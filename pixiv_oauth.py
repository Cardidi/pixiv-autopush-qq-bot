import datetime
import os
import time
from typing import cast as _cast
import log
import log as _log
import pixivpy3 as _pixiv
import config as _config
import gppt as _gppt

_last_testment: int = 0


def _cache_userinfo_path(conf: _config.BotConf) -> str:
    import config
    return config.cache_path + f"/login_info_{conf.pixiv_user_name}.json"


def _fetch_cache(conf: _config.BotConf) -> _gppt.LoginInfo:
    import json
    p = _cache_userinfo_path(conf)
    if os.path.isfile(p):
        with open(p, "r") as login_cache:
            res = _cast(_gppt.LoginInfo, json.load(login_cache))
            _log.debug("Found cached user info.")
            return res
    return None


def _refresh_token(conf: _config.BotConf) -> _gppt.LoginInfo:
    import json

    p = _cache_userinfo_path(conf)
    _log.process(f"Attempting login as '{conf.pixiv_user_name}'")
    if conf.pixiv_user_pwd is None:
        raise ValueError("'pixiv_user_pwd' was required to refresh user info!")

    g = _gppt.GetPixivToken()
    r: _gppt.LoginInfo
    st = 1
    while True:
        try:
            r = g.login(True, conf.pixiv_user_name, conf.pixiv_user_pwd)
            break
        except Exception as e:
            log.failed(f"Failed to login in, Try again in {st}s. Details: {e}")
            time.sleep(st)
            st *= 2
            if st > 120:
                st = 120
            _log.process(f"Attempting login as '{conf.pixiv_user_name}' again")
            continue

    _log.debug(f"Get access_token={r['access_token']}")
    _log.debug(f"Get refresh_token={r['refresh_token']}")

    # Update cache info
    if os.path.exists(p):
        os.remove(p)
    with open(p, "x") as login_cache:
        login_cache.write(json.dumps(r))

    _log.success(f"login as '{conf.pixiv_user_name}'")
    global _last_testment
    import typing
    _last_testment = typing.cast(int, datetime.datetime.now().timestamp())
    return r


def _update_app(app: _pixiv.AppPixivAPI, conf: _config.BotConf, inf: _gppt.LoginInfo):
    if conf.pixiv_user_watch_uid is None:
        conf.pixiv_user_watch_uid = inf["user"]["id"]
    app.set_auth(access_token=inf["access_token"], refresh_token=inf["refresh_token"])


def validate_response(json: dict, warn: bool = True) -> bool:
    if "error" in json:
        if warn:
            _log.warn(f"Request failed with '{json['error']['message']}'")
        return False
    return True


def should_retry_response(app: _pixiv.AppPixivAPI, conf: _config.BotConf, json: dict, warn: bool = True) -> bool:
    if validate_response(json, warn):
        return False
    _log.process("Login info was rejected. Require refreshing.")
    res = _refresh_token(conf)
    _update_app(app, conf, res)
    _log.success("Refreshed. Action should being redo.")
    return True


def token_valid_guard(app: _pixiv.AppPixivAPI, conf: _config.BotConf):
    test = app.user_detail(conf.pixiv_user_watch_uid)
    should_retry_response(app, conf, test, False)


def auto_token_valid_guard(app: _pixiv.AppPixivAPI, conf: _config.BotConf):
    global _last_testment
    import typing
    t = typing.cast(int, datetime.datetime.now().timestamp())
    if t - _last_testment > conf.token_expired_test_interval:
        _log.debug("Token will being test for time expired.")
        token_valid_guard(app, conf)
        _last_testment = t


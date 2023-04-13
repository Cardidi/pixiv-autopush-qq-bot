import threading

import config
from mirai_core import Bot, Updater
from mirai_core.models import Event, Message, Types
import pixiv_action
import pixiv_oauth as oauth
from picdb import *
from pixivpy3 import *
from gppt import LoginInfo
import log
import schedule
import time

_app: AppPixivAPI
_updater: Updater
_bot: Bot
_conf: config.BotConf
_exit = False
_return_val = 0


def send_image():
    list = pixiv_action.fetch_bookmarks(_app, _conf, _conf.check_bookmark_new_sending_limit)
    l = "Sending List:"
    for i in list:
        l += f"\n{i.getParent().getPid()}[{i.getIndex()}]"
    log.debug(l)
    pass


def _create_app() -> AppPixivAPI:
    initapp = AppPixivAPI()
    res: LoginInfo
    refresh = True

    # Cache login info if possible
    res = oauth._fetch_cache(_conf)
    if res is not None:
        log.process("Trying to using cached login info...")
        # Test for connection with environment filling
        initapp.set_auth(access_token=res["access_token"], refresh_token=res["refresh_token"])
        if _conf.pixiv_user_watch_uid is None:
            _conf.pixiv_user_watch_uid = res["user"]["id"]
        test = initapp.user_detail(_conf.pixiv_user_watch_uid)
        # Check if require login again
        refresh = not oauth.validate_response(test, False)
        if refresh:
            log.failed("Cache was reject. Require refreshing.")
        else:
            global _last_testment
            import typing
            from datetime import datetime
            oauth._last_testment = typing.cast(int, datetime.now().timestamp())
            log.success("Cache was accept.")

    if refresh:
        res = oauth._refresh_token(_conf)
        # Set environments
        oauth._update_app(initapp, _conf, res)

    return initapp

def _create_mirai_connection() -> Bot:
    b = Bot(_conf.login_qq, _conf.mirai_host, _conf.mirai_host_port, _conf.mirai_authcation_key, scheme=_conf.mirai_schme)
    return b


def _load_config() -> config.BotConf:
    if config.exist_config() == False:
        config.create_appdata()
        config.create_default_config()
        return None

    try:
        return config.load_config()
    except NotImplementedError | TypeError as e:
        log.failed(e)

    return None

def _serv_create():
    schedule.every(_conf.check_bookmark_new).minute.do(send_image)


def safe_exit(code: int = 0):
    _updater.raise_shutdown()
    _exit = True
    _return_val = code

class _evt_looper(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def _event_looper(self):
        while _return_val == 0 | _exit == False:
            try:
                schedule.run_pending()
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    log.debug("Receive process_kill signal (Ctrl + C).")
                    safe_exit(0)
                    return

                log.failed(f"Found error while process scheduled events: {e}")
                log.print_recent_err()
            time.sleep(_conf.schedule_update_interval)

        def run(self):
            self._event_looper()


if __name__ == '__main__':
    print("Pixiv tacker bot for Mirai - CA2D PROD")
    print("Version: 0")
    print("==== LOGS ====")

    try:
        # Load Config
        log.process("Load config file")
        cnf = _load_config()
        if not isinstance(cnf, config.BotConf):
            log.failed("Please fill config file correctly to run this program!")
            safe_exit(1)
        _conf = cnf
        log.success("Config")

        # Create application essential
        log.process("Load record database")
        load_db()
        log.success("Database")
        log.process("Load pixiv application")
        _app = _create_app()
        log.success("Pixiv Application")

        # Connect to Mirai service
        log.process("Connecting to Mirai service")
        _bot = _create_mirai_connection()
        _updater = Updater(_bot)
        log.success("Mirai")

        # Hook service
        log.process("Hooking self-managed events")
        _serv_create()
        log.success("Self-managed Events")

        # Start Service Loop
        log.success("Start Bot Service")
        timer = _evt_looper()
        timer.start()
        _updater.run()

    except Exception as e:
        log.failed(f"Unhandled Exception (FORCE EXIT): {e}")
        log.print_recent_err()
        _return_val = -1

    except KeyboardInterrupt:
        log.debug("Receive process_kill signal (Ctrl + C).")
        _return_val = 0

    finally:
        clean_up_db()

    log.debug("Exiting Program...")
    exit(_return_val)

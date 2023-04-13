import os.path as path
import os
import yaml
import log

# Path of scripts essential
data_path = "appdata"
cache_path = data_path + "/cache"
config_filepath = data_path + "/config.yml"
database_filepath = data_path + "/info.db"


# Read Config


def exist_config() -> bool:
    return path.exists(config_filepath) & path.isfile(config_filepath) \
        & path.exists(cache_path) & path.isdir(cache_path)


def create_appdata():
    os.makedirs(data_path, exist_ok=True)
    os.makedirs(cache_path, exist_ok=True)


def create_default_config():
    if path.exists(config_filepath):
        os.remove(config_filepath)
    with open(config_filepath, "w") as f:
        f.write("""## Bot
login_qq: '' # Fill before start
        
## User
pixiv_user_name: 'cardidi' # Fill before start
pixiv_user_pwd: '' 

## Filters
show_policy_limited_image: 0 # 0 (Default): Don't show, 1: R18 Only, 2: R18G Only, 3 R18 & R18G
# image_tag_filter_as_whitelist: False
# image_tag_filter:
#   - '0'
# image_uid_filter_as_whitelist: False
# image_uid_filter:
#   - '0'
# image_pid_filter_as_whitelist: False
# image_pid_filter:
#   - '0'
""")


class BotConf:
    # Bot
    login_qq: int = None
    mirai_host: str = '127.0.0.1'
    mirai_host_port: int = 0
    mirai_authcation_key: str = ''
    mirai_schme: str = 'http'
    response_group: list

    # User
    pixiv_user_name: str = None
    pixiv_user_pwd: str = None
    pixiv_user_watch_uid: str = None
    token_expired_test_interval: int = 3000

    # Watcher
    schedule_update_interval: float = 1
    response_group: list = []
    check_bookmark_new: int = 1
    check_bookmark_new_sending_limit: int = 15
    check_bookmark_baseline_uid: str = None
    check_bookmark_restrict: str = "public"

    # Filter
    show_policy_limited_image: int = 0
    image_tag_filter_as_whitelist: bool = False
    image_tag_filter: list = []
    image_uid_filter_as_whitelist: bool = False
    image_uid_filter: list = []
    image_pid_filter_as_whitelist: bool = False
    image_pid_filter: list = []



def load_config() -> BotConf:
    conf = BotConf()
    with open(config_filepath, "r") as cf:
        ycf = yaml.load(cf, Loader=yaml.FullLoader)

        def _load(val: str, type) -> bool:
            if val in ycf:
                v = ycf[val]
                if not isinstance(v, type):
                    raise TypeError(f"'{val}' should be {str(type)}.")
                setattr(conf, val, v)
                return True
            return False

        # Load Config
        if not _load("login_qq", int):
            raise AttributeError("Do not found essential key named 'login_qq' !")

        if not _load("mirai_host", str):
            raise AttributeError("Do not found essential key named 'mirai_host' !")

        if not _load("mirai_host_port", int):
            raise AttributeError("Do not found essential key named 'mirai_host_port' !")

        if not _load("mirai_authcation_key", str):
            raise AttributeError("Do not found essential key named 'mirai_authcation_key' !")

        if not _load("mirai_schme", str):
            raise AttributeError("Do not found essential key named 'mirai_schme' !")

        if not _load("pixiv_user_name", str):
            raise AttributeError("Do not found essential key named 'pixiv_user_name' !")

        if not _load("pixiv_user_pwd", str):
            log.warn("'pixiv_user_pwd' has been configurate as empty, which may cause unsuccessful login.")

        if not _load("pixiv_user_watch_uid", str):
            log.debug("'pixiv_user_watch_uid' has been configurate as empty, which means watching login user. Not "
                      "recommond due to API access limitation.")

        if _load("show_policy_limited_image", int) & conf.show_policy_limited_image != 0:
            log.debug("Bot was required to send R18 or R18G image which may cause some policy issue. Make sure "
                      "your local is accept those kind of content.")

        _load("response_group", list)
        _load("token_expired_test_interval", int)
        _load("schedule_update_interval", float)
        _load("response_group", list)
        _load("check_bookmark_new_interval", int)
        _load("check_bookmark_new_sending_limit", int)
        _load("check_bookmark_baseline_uid", str)
        _load("check_bookmark_restrict", str)
        _load("image_pid_filter_as_whitelist", bool)
        _load("image_tag_filter_as_whitelist", bool)
        _load("image_uid_filter_as_whitelist", bool)
        _load("image_pid_filter", list)
        _load("image_tag_filter", list)
        _load("image_uid_filter", list)

    return conf

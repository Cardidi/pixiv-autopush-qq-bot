import os.path
import sqlite3
import typing
import pixivpy3
import config as _config
import os.path as _path
from pathlib import Path as _Path
from sqlite3 import Connection
from enum import Enum as _enum, unique as _unique

import log
import pixiv_oauth

_con: Connection
_default_db_creation_sql = '''
DROP TABLE IF EXISTS record;
DROP TABLE IF EXISTS record_tag;
DROP TABLE IF EXISTS history;
DROP TABLE IF EXISTS history_details;

CREATE TABLE record(
    pix_image_id varchar(10) NOT NULL,
    pix_image_index int NOT NULL,
    pix_creator_id varchar(9) NOT NULL,
    pix_policy int NOT NULL default 0,
    pix_url varchar(100) NOT NULL,
    pix_download_path varchar(50),
    PRIMARY KEY (pix_image_id, pix_image_index)
);

CREATE TABLE record_tag(
    pix_image_id varchar(10) NOT NULL,
    tag varchar(40) NOT NULL,
    PRIMARY KEY (pix_image_id, tag),
    FOREIGN KEY(pix_image_id) REFERENCES record(pix_image_id)
);

CREATE TABLE history(
    action_id int AUTO_INCREMENT NOT NULL PRIMARY KEY,
    action_type int NOT NULL
);

CREATE TABLE history_details(
    action_id int NOT NULL,
    pix_image_id varchar(10) NOT NULL,
    pix_image_index int NOT NULL,
    PRIMARY KEY (action_id, pix_image_id, pix_image_index),
    FOREIGN KEY (pix_image_id, pix_image_index) REFERENCES record(pix_image_id, pix_image_index)
);
'''


# STRUCTURES

@_unique
class history_action_type(_enum):
    bookmark_modification_post = 0


@_unique
class pic_policy_type(_enum):
    normal = 0
    r18 = 1
    r18g = 2


class ImageRecord:
    _pid: str
    _uid: str
    _indexes: list
    _url: str
    _tags: list
    _policy: pic_policy_type

    def removeDBNonCommit(self):
        conn = get_connection()
        conn.execute("delete from record where pix_image_id=?", (self._pid,))
        conn.execute("delete from record_tag where pix_image_id=?", (self._pid,))

    def writeDBNonCommit(self):
        conn = get_connection()
        self.removeDBNonCommit(conn)
        # Perform new updated info
        for i in self._indexes:
            if isinstance(i, ImageRecordIndex):
                conn.execute("insert into record values(?,?,?,?,?,?)",
                             (self._pid, i._index, self._uid, self._policy, self._url, i._download_url))

        for t in self._tags:
            conn.execute("insert into record_tag values(?,?)", (self._pid, t))

    def isInDBCorrectly(self) -> bool:
        crs = get_connection().cursor()
        crs.execute("select count(*) from record where pix_image_id=?", (self._pid,))
        count = typing.cast(int, crs.fetchone()[0])
        crs.close()
        return count == len(list)

    def getPolicy(self) -> pic_policy_type:
        return self._policy

    def getPid(self) -> str:
        return str(self._pid)

    def getUid(self) -> str:
        return str(self._uid)

    def getRecordIndex(self) -> list:
        return self._indexes

    def getOriginUrl(self) -> str:
        return self._url

    def getTags(self) -> list:
        return self._tags

    def isPublic(self) -> bool:
        return str(self._uid) != "0"


class ImageRecordIndex:
    _index: int
    _download_url: str
    _parent: ImageRecord

    def getIndex(self) -> int:
        return self._index

    def getCacheLocalFilePath(self) -> str:
        p = os.path.basename(self._download_url)
        p = _config.cache_path + f"/{p}"
        return p

    def hasCached(self) -> bool:
        p = self.getCacheLocalFilePath()
        if (p is None) | (not self._parent.isPublic()):
            return False
        return _path.exists(p) & _path.isfile(p)

    def getParent(self) -> ImageRecord:
        return self._parent

    def addActionHistoryNonCommit(self, action_id: int):
        conn = get_connection()
        conn.execute("insert into history_details values (?,?,?)", (action_id, self._parent.getPid(), self._index))

    def getActionHistoryId(self) -> list:
        conn = get_connection()
        result = []
        with conn.cursor() as f:
            f.execute("select action_id from history_details where pix_image_index=? and pix_image_id=?", (self.getParent().getPid(), self.getIndex()))
            l = f.fetchall()
            for i in l:
                result.append(i[0])
        return result


    def createCache(self, app: pixivpy3.AppPixivAPI, conf: _config.BotConf, force: bool = False):
        p = self.getCacheLocalFilePath()
        log.process(f"{self._parent.getPid()}_{self._index} - Download image to {p}'")
        if not self._parent.isPublic():
            log.failed(
                f"{self._parent.getPid()}_{self._index} - Can not perform download due to image was set to non-public")
            return

        if os.path.exists(p):
            if force:
                log.failed(f"{self._parent.getPid()}_{self._index} - Previous cache was found. Do no modification!")
                return
            else:
                log.debug(f"{self._parent.getPid()}_{self._index} - Previous cache will be override.")

        pixiv_oauth.auto_token_valid_guard(app, conf)
        if app.download(url=self._download_url, fname=p):
            log.success(f"{self._parent.getPid()}_{self._index} - Save at {p}")
        else:
            log.success(f"{self._parent.getPid()}_{self._index} - Failed")


class HistoryAction:
    _id: int
    _type: history_action_type
    _details: list

    def getId(self) -> int:
        return self._id

    def getType(self) -> history_action_type:
        return self._type

    def getDetails(self) -> list:
        return self._details


# BASIC METHOD


def clean_up_db():
    global _con
    if _con is None:
        return
    _con.commit()
    _con.close()


def get_connection():
    global _con
    if _con is None:
        raise ReferenceError("Did not load database!")

    return _con


def load_db():
    global _con
    c = False  # Is database new-created
    if not (_path.exists(_config.database_filepath) | _path.isfile(_config.database_filepath)):
        _Path(_config.database_filepath).touch()
        c = True

    _con = sqlite3.Connection(_config.database_filepath)
    if c:
        _con.executescript(_default_db_creation_sql)  # Create new database structure
        _con.commit()


# Utilites


def valid_uid(conf: _config.BotConf, record: ImageRecord) -> bool:
    include = record.getUid() in conf.image_uid_filter
    if conf.image_uid_filter_as_whitelist:
        return include
    return not include


def valid_tag(conf: _config.BotConf, record: ImageRecord) -> bool:
    include = False
    tgs = record.getTags()
    for t in conf.image_tag_filter:
        if t in tgs:
            include = True
            break
    if conf.image_tag_filter_as_whitelist:
        return include
    return not include


def valid_pid(conf: _config.BotConf, record: ImageRecord) -> bool:
    include = record.getPid() in conf.image_pid_filter
    if conf.image_pid_filter_as_whitelist:
        return include
    return not include


def valid_policy(conf: _config.BotConf, record: ImageRecord) -> bool:
    policy = conf.show_policy_limited_image
    target = typing.cast(record.getPolicy(), int)
    if policy == 0:
        return target == 0
    if policy == 1:
        return target <= 1
    if policy == 2:
        return target == 0 | target == 2
    if policy == 3:
        return True
    return False


def get_image_pid(json: dict) -> str:
    if ('type' not in json) | (json["type"] != ("illust" or "manga")):
        return None
    return json["id"]


def create_image_record_from_response_non_commit(json: dict) -> ImageRecord:
    if ('type' not in json) | (json["type"] != ("illust" or "manga")):
        return None

    rec = ImageRecord()
    rec._pid = json["id"]
    rec._uid = str(json["user"]["id"])
    rec._url = f"https://www.pixiv.net/artworks/{rec._pid}"
    rec._policy = 0  # I'm not sure which flags means to policy
    rec._tags = []
    origint_tags = json["tags"]
    for tag in origint_tags:
        rec._tags.append(tag["name"])

    if "original_image_url" in json["meta_single_page"]:
        idx = ImageRecordIndex()
        idx._index = 0
        idx._parent = rec
        idx._download_url = json["meta_single_page"]["original_image_url"]
        rec._indexes = [idx]
    else:
        if ("meta_pages" in json) & (len(json["meta_pages"]) > 0):
            l = []
            ii = 0
            for meta in json["meta_pages"]:
                idx = ImageRecordIndex()
                idx._index = ii
                idx._parent = rec
                idx._download_url = meta["image_urls"]["original"]
                l.append(idx)
                ii += 1
            rec._indexes = l
        else:
            raise ValueError("Given illust details is not valid!")

    rec.removeDBNonCommit()
    rec.writeDBNonCommit()
    return rec


def query_image_record(pid: str) -> ImageRecord:
    con = get_connection()
    # Create ImageRecords.
    imageCrs = con.cursor()
    imageCrs.execute("select * from record where pix_image_id=? order by pix_image_index", (pid,))
    iidx = imageCrs.fetchall()
    if len(iidx) == 0:
        return None  # do no effort on an empty target.

    # Create base object
    f = iidx[0]
    rec = ImageRecord()
    rec._pid = f["pix_image_id"]
    rec._uid = f["pix_creator_id"]
    rec._url = f["pix_url"]
    rec._policy = f["pix_policy"]

    # Create index
    idx_list = []
    idx = 0
    for i in iidx:
        c = ImageRecordIndex()
        c._index = idx
        c._download_url = i["pix_download_path"]
        c._parent = rec
        idx_list.append(c)
    rec._indexes = idx_list
    imageCrs.close()

    # Write tags
    tagCrs = con.cursor()
    tagCrs.execute("select tag from record_tag where pix_image_id=?", (pid,))
    tagTuple = tagCrs.fetchall()
    rec._tags = []
    for t in tagTuple:
        rec._tags.append(t[0])

    tagCrs.close()


def create_action_history_non_commit(action_type: history_action_type, action_details) -> HistoryAction:
    conn = get_connection()
    hid = 0

    # Get top id in history actions.
    with conn.cursor() as tc:
        tc.execute("select action_id from history order by action_id desc limit 1")
        tc_tup = tc.fetchone()
        if tc_tup is not None:
            hid = tc_tup[0]

    # Insert action into database
    conn.execute("insert into history values (?, ?)", (hid, action_type))
    res = HistoryAction()
    res._id = hid
    res._type = action_type

    # if action_details is not None, fill them into db.
    if action_details is not None:
        for d in action_details:
            if isinstance(d, ImageRecordIndex):
                conn.execute("insert into history_details values (?,?,?)", (hid, d.getParent().getPid(), d.getIndex()))
        res._details = action_details

    return res


def query_action_history(action_id: int) -> HistoryAction:
    res = HistoryAction()
    res._details = []
    conn = get_connection()

    # Fetch action basic info
    with conn.cursor() as main:
        main.execute("select * from history where action_id=?", (action_id,))
        mm = main.fetchone()
        if mm is None:
            return None
        res._id = action_id
        res._type = mm[1]

    with conn.cursor() as details:
        details.execute("select pix_image_id, pix_image_index from history_details where action_id=?", (action_id,))
        while True:
            cur = details.fetchone()
            if cur is None:
                break
            id = cur[0]
            index = cur[1]
            pic = query_image_record(id)
            target = pic.getRecordIndex()[index]
            res._details.append(target)

    return res

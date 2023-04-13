import pixiv_oauth as oauth
from picdb import *
import config


def fetch_bookmarks(app: pixivpy3.AppPixivAPI, conf: config.BotConf, count: int) -> list[ImageRecordIndex]:
    conn = get_connection()
    result: list = []
    baseline = conf.check_bookmark_baseline_uid
    while True:
        resp = app.user_bookmarks_illust(user_id=conf.pixiv_user_watch_uid, restrict=conf.check_bookmark_restrict)
        if oauth.should_retry_response(app, conf, resp): continue

        # Start collect content.
        illust = resp["illusts"]
        for i in illust:
            if len(result) >= count:  # Reach desired number.
                break
            # fetch new image of id
            r: ImageRecord
            try:
                r = create_image_record_from_response_non_commit(i)
            except ValueError as e:
                log.debug(f"Illust has been skipped due to invalid json: '{i['id']}'")
                continue

            # Using filter
            if r is None:
                continue
            if r.getPid() == baseline:
                break  # Met baseline means the rest of illust should being disposed.
            valid = valid_pid(conf, r) & valid_tag(conf, r) & valid_uid(conf, r) & valid_policy(conf, r)
            if not valid:
                continue # Skip if not valid

            # fetch actually image.
            for j in r.getRecordIndex():
                if isinstance(j, ImageRecordIndex):
                    hasHistory = j.getActionHistoryId()
                    if len(hasHistory) == 0: # Has not been sent yet.
                        result.append(j)
                if len(result) >= count:  # Reach desired number.
                    break

        if len(result) >= count:  # Reach desired number.
            break

    conn.commit()  # Apply modifications.
    return result


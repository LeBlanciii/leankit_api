import datetime
import json
import logging
import os
import time
from functools import wraps

import requests
from dateutil import parser as date_parser

LEANKIT_URL = os.environ['LEANKIT_URL']

leankit_session = requests.Session()
leankit_session.auth = (os.environ['LEANKITUSERNAME'], os.environ['LEANKITPASSWORD'])
leankit_session.headers = {"Content-Type": "application/json"}

logging.basicConfig(format='{}:%(levelname)s: %(message)s'.format(datetime.datetime.now()), level=logging.INFO)


def retry(tries=13, delay=1, backoff=2, logger=None):
    def deco_retry(f):

        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


@retry()
def move_card(board_id, card, to_lane):
    logging.info("move_card: {} lane: {}".format(card["id"], to_lane))
    leankit_session.post("{}/kanban/api/board/{}/MoveCard/{}/lane/{}/position/1".format(
        LEANKIT_URL, board_id, card['id'], to_lane)).raise_for_status()


@retry()
def block_card(card, reason):
    logging.info("block_card: {} reason: {}".format(card["id"], reason))
    payload = json.dumps({"CardId": card["id"], "IsBlocked": True, "BlockReason": reason or "Not Specified"})
    leankit_session.post("{}/kanban/api/card/update".format(LEANKIT_URL), data=payload).raise_for_status()


@retry()
def add_card(board, lane, title, header="", description="", type_id=None, size=0, url="", tags=[],
             external_system_name=""):
    params = {"boardId": str(board),
              "title": title,
              "laneId": str(lane),
              "typeId": str(type_id),
              "description": description,
              "index": 1,
              "size": size,
              "blockReason": "",
              "externalLink": {"label": external_system_name, "url": url},
              "tags": tags,
              "customId": header,
              }
    response = leankit_session.post("{}/io/card/".format(LEANKIT_URL), data=json.dumps(params))
    if response.status_code == 201:
        logging.info("added card: {} to lane: {}".format(title, lane))
        return response.json()['id']
    logging.error("Error adding card: {}".format(response.json()))
    response.raise_for_status()


@retry()
def get_card(card_id):
    return leankit_session.get("{}/io/card/{}".format(LEANKIT_URL, card_id)).json()


@retry()
def get_children(card_id):
    return leankit_session.get("{}/io/card/{}/connection/children".format(LEANKIT_URL, card_id)).json()["cards"]


@retry()
def get_cards(board=None, type=None, lane_class_types=None, lanes=None,
              since=None, deleted=False, only=None, search=None, limit=5000, offset=0):
    params = {}
    for k, v in locals().items():
        if not v:
            continue
        if isinstance(v, list):
            params[k] = ','.join(v)
            continue
        params[k] = v
    return leankit_session.get("{}/io/card/".format(LEANKIT_URL), params=params).json()['cards']


@retry()
def delete_card(card):
    logging.warning("delete card {}".format(card["id"]))
    logging.warning("Uncomment to complete".format(card["id"]))
    leankit_session.delete("{}/io/card/{}".format(LEANKIT_URL, card['id']))


@retry()
def get_board(board_id):
    url = "{}/io/board/{}".format(LEANKIT_URL, board_id)
    return leankit_session.get(url).json()


@retry()
def get_task_board(board_id, card_id):
    url = "{}/kanban/api/v1/board/{}/card/{}/taskboard".format(LEANKIT_URL, board_id, card_id)
    return leankit_session.get(url).json()['ReplyData'][0]


@retry()
def move_task(board_id, card_id, task_id, lane_id):
    url = "{}/kanban/api/v1/board/{}/move/card/{}/tasks/{}/lane/{}".format(
        LEANKIT_URL, board_id, card_id, task_id, lane_id)
    r = leankit_session.post(url)
    r.raise_for_status()


def reset_card_tasks(board_id, card_id):
    tb = get_task_board(board_id, card_id)
    if not tb:
        return
    tasks = []
    backlog_lane_id = tb['Lanes'][0]['Id']
    for l in tb['Lanes']:
        tasks.extend(l['Cards'])
    for t in tasks:
        move_task(board_id, card_id, t['Id'], backlog_lane_id)


@retry()
def update_header(card_id, title):
    logging.info("update header: {}  title: {}".format(card_id, title))
    r = leankit_session.patch("{}/io/card/{}".format(LEANKIT_URL, card_id),
                              data=json.dumps([{"op": "replace", "path": "/customId", "value": str(title)}]))
    r.raise_for_status()


@retry()
def update_custom_field(card_id, path, value):
    logging.info("update custom field:\nid:{}\npath:{}\nvalue:{}".format(card_id, path, value))
    r = leankit_session.patch("{}/io/card/{}".format(LEANKIT_URL, card_id),
                              data=json.dumps([{"op": "replace", "path": path, "value": value}]))
    r.raise_for_status()


@retry()
def update_planned_finish(card_id, date):
    """date: yyyy-mm-dd """
    logging.info("update planned finish: {}  date: {}".format(card_id, date))
    r = leankit_session.patch("{}/io/card/{}".format(LEANKIT_URL, card_id),
                              data=json.dumps([{"op": "replace", "path": "/plannedFinish", "value": str(date)}]))
    r.raise_for_status()


@retry()
def change_card_type(card_id, card_type):
    """
    :param card_id: Int
    :param card_type: Int or str: card type id
    """
    r = leankit_session.patch("{}/io/card/{}".format(LEANKIT_URL, card_id),
                              data=json.dumps([{"op": "replace", "path": "/typeId", "value": str(card_type)}]))
    if r.status_code == 200:
        logging.info("Changed card {} type to {}".format(card_id, card_type))
    else:
        logging.error(r.json())

    # from leankit.api import *
    # excards = get_cards(board=30502076986646, type=30502076993718)
    # for card in excards:
    #     change_card_type(card["id"], 30502076992872)


def is_card_completed(card):
    return card['lane']['laneClassType'] == 'archive'


def is_card_completed_recently(card, days_ago=30):
    if not card['actualFinish']:
        return
    date_completed = date_parser.parse(card['actualFinish']).replace(tzinfo=None)
    return (datetime.datetime.today() - date_completed).days < days_ago


@retry()
def remove_planned_finish(card_id):
    logging.info("remove planned finish: {}".format(card_id))
    r = leankit_session.patch("{}/io/card/{}".format(LEANKIT_URL, card_id),
                              data=json.dumps([{"op": "remove", "path": "/plannedFinish"}]))
    r.raise_for_status()


@retry()
def card_history(board_id, card_id):
    return leankit_session.get("{}/kanban/api/card/history/{}/{}".format(
        LEANKIT_URL, board_id, card_id)).json()["ReplyData"][0]


@retry()
def lane_history(board_id, limit=1000, offset=0):
    return leankit_session.get(
        '{}/io/reporting/export/cardpositions.json?boardId={}&limit={}&offset={}'.format(LEANKIT_URL, board_id, limit,
                                                                                         offset)).json()

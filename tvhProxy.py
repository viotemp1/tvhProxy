# refresh guide "http://x.x.x.x/cgi-bin/HttpControl/HttpControlApp?OPTION=1&Method=ScanEPG&ChannelID=All

from gevent import monkey

monkey.patch_all()

import time
import os
import io
import requests, json, xmltodict
import traceback
from gevent.pywsgi import WSGIServer
from flask import Flask, Response, request, jsonify, abort, render_template
from apscheduler.schedulers.background import BackgroundScheduler
from lxml import etree

try:
    to_unicode = unicode
except NameError:
    to_unicode = str

app = Flask(__name__)

# URL format: <protocol>://<username>:<password>@<hostname>:<port>, example: https://test:1234@localhost:9981
config = {
    "bindAddr": os.environ.get("TVH_BINDADDR") or "",
    # 'tvhURL': os.environ.get('TVH_URL') or 'http://test:test@localhost:9981',
    "tvhURL": os.environ.get("TVH_VBOX_URL") or "http://localhost:55555",
    "tvhProxyURL": os.environ.get("TVH_PROXY_URL") or "http://localhost",
    "tunerCount": os.environ.get("TVH_TUNER_COUNT") or 2,  # number of tuners in tvh
    "guideRefreshInterval_h": os.environ.get("TVH_GUIDE_REFRESH_INTERVAL_H") or 24,
}

discoverData = {
    "FriendlyName": "VboxTV Proxy",
    "Manufacturer": "VBOX",
    "ModelNumber": "Custom",
    "FirmwareName": "hdhomeruntc_pal",
    "TunerCount": int(config["tunerCount"]),
    "FirmwareVersion": "20150826",
    "DeviceID": "12345678",
    "DeviceAuth": "test1234",
    "BaseURL": "%s" % config["tvhProxyURL"],
    "LineupURL": "%s/lineup.json" % config["tvhProxyURL"],
}


@app.route("/discover.json")
def discover():
    return jsonify(discoverData)


@app.route("/lineup_status.json")
def status():
    return jsonify(
        {
            "ScanInProgress": 0,
            "ScanPossible": 1,
            "Source": "Cable",
            "SourceList": ["Cable"],
        }
    )


@app.route("/lineup.json")
def lineup():
    lineup = []

    # print("lineup - started")
    channel_dict = _get_channels()

    if channel_dict and len(channel_dict) > 0:
        for ch in _get_channels():
            # print(c)
            lineup_c = {
                "GuideNumber": str(ch["@id"]),
                "GuideName": ch["display-name"][0],
                "URL": ch["url"]["@src"],
            }
            # print("lineup_c", lineup_c)
            lineup.append(lineup_c)

    # print(f"lineup - ended {len(lineup)} channels")
    return jsonify(lineup)


@app.route("/lineup.post", methods=["GET", "POST"])
def lineup_post():
    return ""


@app.route("/")
@app.route("/device.xml")
def device():
    return render_template("device.xml", data=discoverData), {
        "Content-Type": "application/xml"
    }


@app.route("/vboxXmltv.xml")
def vboxXmltv():
    response_json = _load_xml_guide()
    response_xml = xmltodict.unparse(response_json)
    # print(response_xml)
    return Response(response_xml, mimetype='application/xml')
    # return render_template("vboxXmltv.xml", data=response_xml), {
    #     "Content-Type": "application/xml"
    # }


def _get_channels():
    response_json = _load_xml_guide()
    return response_json["tv"]["channel"]

def _save_xml_guide():
    url = f"{config['tvhURL']}/vboxXmltv.xml"
    print("_save_xml_guide started")
    try:
        # response = requests.get(url)
        with requests.get(url) as response:
            decoded_response = response.content.decode("utf-8")
            # print("decoded_response", decoded_response)
            response_json = json.loads(json.dumps(xmltodict.parse(decoded_response)))
            i = 0
            for ch in response_json["tv"]["channel"]:
                i += 1
                ch["old_id"] = ch["@id"]
                ch["@id"] = f'{i}-{ch["display-name"][0].strip().replace(" ", "_")}'
                ch["LCN"] = ch["display-name"][4]
                ch["display-name"][4] = ch["display-name"][0]
                for epg in response_json["tv"]["programme"]:
                    if epg["@channel"] == ch["old_id"]:
                        epg["@channel"] = ch["@id"]
            
            with io.open("vboxXmltv.json", "w", encoding="utf8") as outfile:
                str_ = json.dumps(
                    response_json, separators=(",", ": "), ensure_ascii=False
                )
                outfile.write(to_unicode(str_))
            print("_save_xml_guide Guide downloaded")
            
    except Exception as e:
        print("_save_xml_guide Error")
        print("\n".join(traceback.format_exc().split("\n")[:6]))
    
sched = BackgroundScheduler(daemon=True)
sched.add_job(_save_xml_guide, "interval", hours=config["guideRefreshInterval_h"])
sched.start()

def _load_xml_guide():
    with open("vboxXmltv.json") as data_file:
        data_loaded = json.load(data_file)
    return data_loaded


if __name__ == "__main__":
    print("Started tvhProxy")
    _save_xml_guide()
    http = WSGIServer((config["bindAddr"], 5004), app.wsgi_app)
    http.serve_forever()
    print("Finished tvhProxy")

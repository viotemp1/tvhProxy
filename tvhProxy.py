from gevent import monkey

monkey.patch_all()

import time
import os
import requests, json, xmltodict
from gevent.pywsgi import WSGIServer
from flask import Flask, Response, request, jsonify, abort, render_template

app = Flask(__name__)

# URL format: <protocol>://<username>:<password>@<hostname>:<port>, example: https://test:1234@localhost:9981
config = {
    "bindAddr": os.environ.get("TVH_BINDADDR") or "",
    # 'tvhURL': os.environ.get('TVH_URL') or 'http://test:test@localhost:9981',
    "tvhURL": os.environ.get("TVH_URL") or "http://localhost:55555",
    "tvhProxyURL": os.environ.get("TVH_PROXY_URL") or "http://localhost",
    "tunerCount": os.environ.get("TVH_TUNER_COUNT") or 2,  # number of tuners in tvh
    "tvhWeight": os.environ.get("TVH_WEIGHT") or 300,  # subscription priority
    "chunkSize": os.environ.get("TVH_CHUNK_SIZE")
    or 1024 * 1024,  # usually you don't need to edit this
    "streamProfile": os.environ.get("TVH_PROFILE")
    or "pass",  # specifiy a stream profile that you want to use for adhoc transcoding in tvh, e.g. mp4
}

discoverData = {
    "FriendlyName": "VboxTV Proxy",
    "Manufacturer": "Silicondust",
    "ModelNumber": "HDTC-2US",
    "FirmwareName": "hdhomeruntc_atsc",
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

    for c in _get_channels():
        print(c)
        lineup_c = {"GuideNumber": str(c["@id"]), "GuideName": c["display-name"][0], "URL": c["url"]["@src"]}
        print("lineup_c", lineup_c)
        lineup.append(lineup_c)

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


def _get_channels():
    # url = '%s/api/channel/grid?start=0&limit=999999' % config['tvhURL']
    url = f"{config['tvhURL']}/vboxXmltv.xml"
    # print("_get_channels", url)
    try:
        response = requests.get(url)
        decoded_response = response.content.decode("utf-8")
        # print("decoded_response", decoded_response)
        response_json = json.loads(json.dumps(xmltodict.parse(decoded_response)))
        print("response_json", response_json["tv"].keys())
        return response_json["tv"]["channel"]

    except Exception as e:
        print("An error occured: " + repr(e))


if __name__ == "__main__":
    print("Started tvhProxy")
    http = WSGIServer((config["bindAddr"], 5004), app.wsgi_app)
    http.serve_forever()
    print("Finished tvhProxy")

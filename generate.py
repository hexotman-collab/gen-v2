import os
import sys
import time
import base64
import random
import json
import codecs
import re
import string
import uuid
from datetime import datetime
import requests
import hmac
import hashlib
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from flask import Flask, request, jsonify

# تعطيل التحذيرات
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# الثوابت والإعدادات
# ==========================================
RELEASE_VERSION = "OB55"
API_HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
API_SECRET_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
AES_KEY_G = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV_G = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

REGION_LANG = {"ME": "ar", "BD": "bn", "IND": "hi", "PK": "ur", "SG": "en", "ID": "id"}

# إعدادات التفعيل
GUEST_URL = "https://100067.connect.garena.com/oauth/guest/token/grant"
CLIENT_ID = "100067"
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
GUEST_HEADERS = {
    "Host": "100067.connect.garena.com",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "close",
}
PLAY_PACKAGE = "com.dts.freefireth"
LOGIN_REGION = "ME"
VERSION_URL = ("https://version.ggwhitehawk.com/live/ver.php?version={v}&lang={lang}&device=android"
               "&channel=android&appstore=googleplay&region={region}&whitelist_version=1.3.0"
               "&whitelist_sp_version=1.0.0")
FALLBACK_VERSION = ("OB55", "1.132.9", "")
AES_KEY = b"Yg&tc%DEuh6%Zc^8"
AES_IV = b"6oyZDr22E3ychjM%"

DATADOME_CID = "FWTNdJThVpQebS2UwFDDVuTDUrooDRONkwc3RotkozZEl36Ud9amFYFASlPQMF~5P0rgDg1HOU~kVRzCxF6SzKLxq~n1woK49aR5JKDK6WeO1sPcQ1W41MJLWf0MurjT"
DATADOME_DDK = "AE3F04AD3F0D3A462481A337485081"

# ==========================================
# دوال المولد (Helper Functions)
# ==========================================
def encode_varint(n):
    if n < 0: return b''
    result = []
    while True:
        byte = n & 0x7F
        n >>= 7
        if n: byte |= 0x80
        result.append(byte)
        if not n: break
    return bytes(result)

def create_proto_field(field_num, value):
    if isinstance(value, int):
        return encode_varint((field_num << 3) | 0) + encode_varint(value)
    elif isinstance(value, (str, bytes)):
        encoded_val = value.encode() if isinstance(value, str) else value
        return encode_varint((field_num << 3) | 2) + encode_varint(len(encoded_val)) + encoded_val
    return b''

def build_proto(fields):
    return b''.join(create_proto_field(k, v) for k, v in fields.items())

def encrypt_api(plain_hex):
    cipher = AES.new(AES_KEY_G, AES.MODE_CBC, AES_IV_G)
    return cipher.encrypt(pad(bytes.fromhex(plain_hex), AES.block_size)).hex()

def generate_password():
    return f"AlliFF_VIP{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

def get_datadome_cookie():
    try:
        url = "https://api-sdk.datadome.co/sdk/"
        payload = {
            'cid': DATADOME_CID, 'ddv': "1.13.9", 'ddvc': "4.0.42", 'ddk': DATADOME_DDK,
            'request': "https://100067.connect.garena.com/api/v2/oauth/guest:register",
            'os': "Android", 'osr': "15", 'osn': "VANILLA_ICE_CREAM", 'osv': "35",
            'ua': "GarenaMSDK/4.0.42(25028RN03A ;Android 15;ar;EG;app 1.128.2 2019120828;)",
            'screen_x': "1640", 'screen_y': "720", 'screen_d': "320",
            'events': "[{\"id\":1, \"message\":\"response validation\", \"source\":\"sdk\", \"date\":" + str(int(time.time() * 1000)) + "}]",
            'camera': "{\"auth\":\"false\", \"info\":\"{}\"}", 'mdl': "25028RN03A",
            'prd': "serenity_global", 'mnf': "Xiaomi", 'dev': "serenity", 'hrd': "serenity",
            'fgp': "Redmi/serenity_global/serenity:15/AP3A.240905.015.A2/A15.0.26.0.VGWMIXM:user/release-keys",
            'tgs': "release-keys", 'inte': "android-java-okhttp"
        }
        headers = {'User-Agent': "okhttp/4.12.0", 'Accept-Encoding': "gzip"}
        response = requests.post(url, data=payload, headers=headers, timeout=10, verify=False)
        try:
            js = response.json()
            cookie_str = js.get("cookie", "")
            match = re.search(r'datadome=([^;]+)', cookie_str)
            if match: return match.group(1)
        except: pass
        cookie = response.cookies.get("datadome")
        if cookie: return cookie
        set_cookie = response.headers.get("Set-Cookie", "")
        match = re.search(r'datadome=([^;]+)', set_cookie)
        if match: return match.group(1)
        return None
    except: return None

def major_login(access_token, open_id, lang):
    try:
        dT = bytes.fromhex('1a13323032362d30392d32382031363a33333a3039220966726565206669726528013a07312e3133322e38423e416e64726f6964204f53203135202f204150492d33352028415033412e3234303930352e3031352e41322f4131352e302e32362e302e5647574d49584d294a0848616e6468656c6452094d544e2053595249415a1243617272696572446174614e6574776f726b60e80c68d00572033332307a1d41524d3634204650204153494d4420414553207c2031383230207c20388001d21d8a01084d616c692d47353792013e4f70656e474c20455320332e322076312e72343970312d3034656163302e63383264376466616662353534653435316437303436356139613231666139389a012b476f6f676c657c34383535623136372d616539622d346237622d393531642d353234636336343461313962a2010c34362e35382e3137312e3639aa01026172b201203435393935623533323538333730306231393264643965356261646335316539ba010134c2010848616e6468656c64ca01115869616f6d69203235303238524e303341d201024d45ea014032383438303866316233326531653538343861303464666163303735633462633439613637613938646539303731356462343265313461316134666539663566f00101ca02094d544e205359524941d202023347ca03206538396231353865346263663938386562643039656238336635333738653837e00387df06e803cac701f003a50a8004cac801880487df069004cac801980487df06c80403d2045a2f646174612f6170702f7e7e35745f77707645586d6e3153656d6a757853337251673d3d2f636f6d2e6474732e667265656669726574682d56386e6233734e7a4b4a696a707a75737a55784c78773d3d2f6c69622f61726d3634e00401ea047a62386530636435653239356565653432663538363064336338366534383364647c2f646174612f6170702f7e7e35745f77707645586d6e3153656d6a757853337251673d3d2f636f6d2e6474732e667265656669726574682d56386e6233734e7a4b4a696a707a75737a55784c78773d3d2f626173652e61706bf00403f804028a050236349a050a32303139313231323239b205094f70656e474c455332b805ff3fc00504e0059b9501ea0507616e64726f6964f205704b717348547943694835645553466250354270506a44536e4f7235426652544d57323133433177397558326553476f6b317756356970464777385175503238326266496971724f4676364746766c4341794941384336787236483474316d35394933664e6153666f4466563435425748f805e7e40682062d7b226375725f72617465223a5b36302c39302c3132305d2c22737570706f72745f65746332223a66616c73657d8806019006019a060134a2060134b206094352171554095b5434c006f87bc80601d2068a0168747470733a2f2f646c2e616b2e66726565666972656d6f62696c652e636f6d2f6c6976652f4142486f74557064617465732f7c68747470733a2f2f636f72652d616b2e66726565666972656d6f62696c652e636f6d2f6c6976652f4142486f74557064617465732f7c3231316339333331363866353539303263376466626664386334653239353764da0612312e34323762356638316437323161343430')
        dT = dT.replace(b'2026-06-29 13:42:51', str(datetime.now())[:-7].encode())
        dT = dT.replace(b'284808f1b32e1e5848a04dfac075c4bc49a67a98de90715db42e14a1a4fe9f5f', access_token.encode())
        dT = dT.replace(b'45995b532583700b192dd9e5badc51e9', open_id.encode())
        data = bytes.fromhex(encrypt_api(dT.hex()))
        response = requests.post("https://loginbp.ppmainecoonghj.com/MajorLogin", headers={
            'User-Agent': "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            'Accept-Encoding': "deflate, gzip", 'X-GA-SV': str(int(time.time())),
            'Authorization': "Bearer", 'X-GA': "v1 1", 'ReleaseVersion': "OB55",
            'Content-Type': "application/x-www-form-urlencoded", 'X-Unity-Version': "2018.4.12f1"
        }, data=data, verify=False, timeout=10)
        if response.status_code == 200:
            jwt_start = response.text.find("eyJ")
            if jwt_start != -1:
                jwt_token = response.text[jwt_start:]
                second_dot = jwt_token.find(".", jwt_token.find(".") + 1)
                if second_dot != -1:
                    jwt_token = jwt_token[:second_dot + 44]
                    payload_part = jwt_token.split('.')[1]
                    data_json = json.loads(base64.urlsafe_b64decode(payload_part + '=' * (4 - len(payload_part) % 4)))
                    acc_id = data_json.get('account_id') or data_json.get('external_id')
                    if acc_id:
                        return {"account_id": str(acc_id), "jwt_token": jwt_token}
    except: pass
    return None

# ==========================================
# دوال التفعيل (FOYSAL)
# ==========================================
def encrypt_foysal(plain: bytes) -> bytes:
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain, AES.block_size))

def enc_varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | 0x80 if n else b)
        if not n: return bytes(out)

def build_proto_foysal(fields):
    parts = []
    for k, v in fields.items():
        if isinstance(v, dict):
            x = build_proto_foysal(v)
            parts.append(enc_varint(k << 3 | 2) + enc_varint(len(x)) + x)
        elif isinstance(v, int):
            parts.append(enc_varint(k << 3) + enc_varint(v))
        else:
            x = v.encode() if isinstance(v, str) else v
            parts.append(enc_varint(k << 3 | 2) + enc_varint(len(x)) + x)
    return b"".join(parts)

def _rv(b, i):
    shift = res = 0
    while True:
        if i >= len(b): raise ValueError("eof")
        c = b[i]; i += 1; res |= (c & 0x7F) << shift
        if not c & 0x80: return res, i
        shift += 7
        if shift > 70: raise ValueError("varint")

def parse_message(b, depth=0):
    out, i = {}, 0
    while i < len(b):
        key, i = _rv(b, i)
        fn, wt = key >> 3, key & 7
        if fn == 0: raise ValueError("field0")
        if wt == 0: v, i = _rv(b, i)
        elif wt == 1: v = int.from_bytes(b[i:i + 8], "little"); i += 8
        elif wt == 5: v = int.from_bytes(b[i:i + 4], "little"); i += 4
        elif wt == 2:
            ln, i = _rv(b, i)
            raw = b[i:i + ln]
            if len(raw) != ln: raise ValueError("trunc")
            i += ln
            v, txt = raw, None
            try: txt = raw.decode("utf-8")
            except: pass
            if txt and txt.isprintable(): v = txt
            else:
                nested = None
                if depth < 6 and raw:
                    try: nested = parse_message(raw, depth + 1)
                    except: nested = None
                if nested: v = nested
                elif txt and all(ch.isprintable() or ch in "\n\r\t" for ch in txt): v = txt
        else: raise ValueError("wiretype")
        out.setdefault(fn, []).append(v)
    return out

def g(msg, fn, default=None):
    if not isinstance(msg, dict): return default
    v = msg.get(fn)
    return v[0] if v else default

_DEVICES = [
    ("Samsung", "SM-G998B", "Adreno (TM) 660", "Android OS 12 / API-31"),
    ("Xiaomi", "2201122G", "Adreno (TM) 730", "Android OS 13 / API-33"),
    ("Realme", "RMX3700", "Mali-G710", "Android OS 14 / API-34"),
]

def get_device(seed):
    r = random.Random(str(seed))
    brand, model, gpu, osv = r.choice(_DEVICES)
    return {"unique_device_id": f"Google|{uuid.UUID(int=r.getrandbits(128), version=4)}", "model": model, "gpu": gpu, "os": osv}

_ver = {}
def version_config(region=None):
    region = (region or LOGIN_REGION).upper()
    if region in _ver: return _ver[region]
    app_v = FALLBACK_VERSION[1]
    try:
        from google_play_scraper import app as play_app
        app_v = play_app(PLAY_PACKAGE).get("version") or app_v
    except: pass
    try:
        url = VERSION_URL.format(v=app_v, lang=REGION_LANG.get(region, "en"), region=region)
        d = requests.get(url, timeout=10, verify=False).json()
        su, rv, lr = d.get("server_url"), d.get("remote_version"), d.get("latest_release_version")
        if su and rv and lr:
            gops = [u.strip() for u in (d.get("gop_url") or "").split(";") if u.strip()]
            _ver[region] = (lr, rv, su, gops[0] if gops else "", app_v)
            return _ver[region]
    except: pass
    _ver[region] = (FALLBACK_VERSION[0], FALLBACK_VERSION[1], "https://loginbp.ggpolarbear.com", "", FALLBACK_VERSION[1])
    return _ver[region]

def get_access_token(uid, password, retries=4):
    data = {"uid": str(uid), "password": password, "response_type": "token", "client_type": "2", "client_secret": CLIENT_SECRET, "client_id": CLIENT_ID}
    for n in range(1, retries + 1):
        try:
            r = requests.post(GUEST_URL, headers=GUEST_HEADERS, data=data, timeout=15)
            if r.status_code == 200:
                d = r.json()
                if d.get("open_id") and d.get("access_token"): return d["open_id"], d["access_token"], d.get("platform", 4)
            elif r.status_code == 429: time.sleep(1.5 * n); continue
        except: pass
        time.sleep(0.7)
    return None, None, None

def build_payloads(open_id, access_token, platform, client_ver, device_id):
    p = {3: str(datetime.now())[:-7], 4: "free fire", 5: 1, 7: str(client_ver), 8: "Android OS 14 / API-34 (UP1A.231005.007/E135FXXSEEZE2)", 9: "Handheld", 11: "CarrierDataNetwork", 12: 1672, 13: 750, 14: "338", 15: "ARMv7 VFPv3 NEON | 2002 | 8", 16: 3702, 17: "Mali-G52", 18: "OpenGL ES 3.2 v1.r38p1-01bet0-mbs2v41_0.6d20ec041e51b2f2d25dfc265586ebe8", 19: device_id, 20: "104.28.197.151", 21: "en", 22: str(open_id), 23: str(platform), 24: "Handheld", 25: "samsung SM-E135F", 26: "ME", 29: str(access_token), 30: 1, 42: "Cellular", 57: "7428b253defc164018c604a1ebbfebdf", 60: 52037, 61: 5355, 62: 3723, 63: 3, 64: 5483, 65: 52037, 66: 5483, 67: 52037, 73: 2, 74: "/data/app/~~yACsV8QOk9OexgajWQP30A==/com.dts.freefireth-Bi_wPVrrhYM2nYncc29q7Q==/lib/arm", 76: 1, 77: "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~yACsV8QOk9OexgajWQP30A==/com.dts.freefireth-Bi_wPVrrhYM2nYncc29q7Q==/base.apk", 78: 3, 79: 1, 81: "32", 83: "2019121229", 86: "OpenGLES2", 87: 8191, 88: int(platform), 92: 16091, 93: "android", 94: "KqsHT3Yeqo3RLRl8efNiL3aL/1SHwlSrtK0DwNAqdkNBQz70TeVy+icaIwuR3UK4b65Uf3IG5xBFEv0uu+jQZI+rOYCmNCsXjJT4QcZaYgoaaUGG", 95: 111107, 96: "{\"cur_rate\":null,\"support_etc2\":false}", 97: 1, 98: 1, 99: str(platform), 100: str(platform), 102: "4503454457550c0766", 104: 53792, 105: 1, 106: "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|https://core-bs.ggpolarbear.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462", 107: "c8e41b7a93f02d56e1a94c7b8203f5d1"}
    q = dict(p); q[90], q[91], q[99], q[103] = "Khulna", "D", "0", 1
    return encrypt_foysal(build_proto_foysal(p)), encrypt_foysal(build_proto_foysal(q))

def send_majorlogin(payload, release, server_url):
    h = {"Accept": "*/*", "Authorization": "Bearer ", "Content-Type": "application/x-www-form-urlencoded", "ReleaseVersion": str(release), "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)", "X-GA": "v1 1", "X-GA-SV": str(int(time.time())), "X-Unity-Version": "2018.4.12f1"}
    try:
        r = requests.post(server_url.rstrip("/") + "/MajorLogin", headers=h, data=payload, timeout=15, verify=False)
        if r.status_code != 200: return None
        c = r.content
        if len(c) < 200: return None
        best, best_score = None, -1
        for off in [64, 0, 48, 32, 80, 16, 128, 8, 96, 60, 56, 40, 24, 20, 12, 4]:
            if off >= len(c): continue
            try: m = parse_message(c[off:])
            except: continue
            tok = g(m, 8); has_jwt = isinstance(tok, str) and tok.count(".") >= 2; has_url = isinstance(g(m, 10), str)
            score = len(m) + (100 if has_jwt else 0) + (50 if has_url else 0)
            if score > best_score: best, best_score = m, score
            if has_jwt and has_url: break
        tok = g(best, 8) if best else None
        if not (isinstance(tok, str) and tok.count(".") >= 2): return None
        return best
    except: pass
    return None

def send_getlogin(payload, server_url, token, release):
    h = {"Accept": "*/*", "Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded", "ReleaseVersion": str(release), "User-Agent": "UnityPlayer/2018.4.12f1", "X-GA": "v1 1", "X-GA-SV": str(int(time.time())), "X-Unity-Version": "2018.4.12f1"}
    try:
        r = requests.post(server_url.rstrip("/") + "/GetLoginData", headers=h, data=payload, timeout=10, verify=False)
        if r.status_code != 200: return None
        for off in [0, 64, 48, 32, 80, 16, 128, 8, 96]:
            if off >= len(r.content): continue
            try: t = parse_message(r.content[off:])
            except: continue
            if len(t) >= 3: return t
    except: pass
    return None

def login_guest(uid, password, region="ME"):
    vc = version_config(region)
    if not vc: return None
    release, client_ver, server_url, _gop, _app_v = vc
    open_id, access_token, platform = get_access_token(uid, password)
    if not access_token: return None
    mp, lp = build_payloads(open_id, access_token, platform, client_ver, get_device(open_id)["unique_device_id"])
    m = send_majorlogin(mp, release, server_url)
    if not m: return None
    jwt, srv = g(m, 8), g(m, 10) or server_url
    t = send_getlogin(lp, srv, jwt, release)
    if not t: return None
    acc_id = g(m, 1); nick = g(t, 4)
    return {"uid": uid, "account_id": acc_id, "region": g(m, 2) or g(t, 3) or region, "token": jwt, "nickname": nick if isinstance(nick, str) and nick else f"Player_{acc_id}", "level": g(t, 6, 1), "exp": g(t, 7, 0)}

# ==========================================
# دالة إنشاء الحساب (المولد)
# ==========================================
def create_account(region, prefix):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            session = requests.Session()
            password = generate_password()
            datadome_cookie = get_datadome_cookie()
            if not datadome_cookie: time.sleep(0.5); continue

            payload_register = json.dumps({"app_id": 100067, "client_type": 2, "password": password, "source": 2}, separators=(',', ':'))
            signature = hmac.new(API_SECRET_KEY.encode(), payload_register.encode(), hashlib.sha256).hexdigest()
            headers_reg = {
                "User-Agent": "GarenaMSDK/4.0.44(25028RN03A ;Android 15;ar;EG;app 1.132.1 2019121229;)",
                "Connection": "Keep-Alive", "Accept": "application/json", "Accept-Encoding": "gzip",
                "Authorization": f"Signature {signature}", "Content-Type": "application/json; charset=utf-8",
                "Cookie": f"datadome={datadome_cookie}", "Host": "100067.connect.garena.com",
            }
            resp_reg = session.post("https://100067.connect.garena.com/api/v2/oauth/guest:register", headers=headers_reg, data=payload_register, timeout=10, verify=False)
            if resp_reg.status_code != 200: continue
            reg_json = resp_reg.json()
            if reg_json.get("code") != 0: continue
            uid = reg_json['data']['uid']

            payload_token = json.dumps({"client_id": 100067, "client_secret": API_HEX_KEY, "client_type": 2, "device_id": "02-344afb0e-593c-40b7-92f2-171972f74807", "password": password, "response_type": "token", "uid": uid}, separators=(',', ':'))
            signature2 = hmac.new(API_SECRET_KEY.encode(), payload_token.encode(), hashlib.sha256).hexdigest()
            headers_tok = {
                "User-Agent": "GarenaMSDK/4.0.44(25028RN03A ;Android 15;ar;EG;app 1.132.1 2019121229;)",
                "Connection": "Keep-Alive", "Accept": "application/json", "Accept-Encoding": "gzip",
                "Content-Type": "application/json; charset=utf-8", "Cookie": f"datadome={datadome_cookie}",
                "Host": "100067.connect.garena.com",
            }
            resp_tok = session.post("https://100067.connect.garena.com/api/v2/oauth/guest/token:grant", headers=headers_tok, data=payload_token, timeout=10, verify=False)
            if resp_tok.status_code != 200: continue
            tok_json = resp_tok.json()
            if tok_json.get("code") != 0: continue
            access_token = tok_json['data']['access_token']
            open_id = tok_json['data']['open_id']

            keystream = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
            field = codecs.decode(''.join(chr(ord(open_id[i]) ^ keystream[i % len(keystream)]) for i in range(len(open_id))).encode('unicode_escape').decode('utf-8'), 'unicode_escape').encode('latin1')
            name = f"{prefix}{random.randint(1000, 9999)}"
            lang = REGION_LANG.get(region.upper(), "en")
            
            proto_data = build_proto({
                1: name, 2: access_token, 3: open_id, 5: 102000007, 6: 4, 7: 1, 13: 1, 14: field,
                15: lang, 16: 1, 17: 1, 20: "1.132.6", 21: 1,
                22: bytes.fromhex('474752450101010067020000a6a42db7bc5516876af3d1ba4adc337bac558af092eb3757d59d65c9323bba42c6593a48b74f33b2b5b3dc45cbd7ac02040db58f394045be4835213e12c35e5566445a5224f39d205fcf91c0e6bec797e7b3968ac00e90d7500b5865828a9d6f2091c3070f5319a130748e407ed57e6638974670ac045631b3d08c310cf1256cebcf1aed2d97d177534603d1c95d9c5d698340e797e72aa7ecc67a33122e48b0dfda050a1649586aca5e979be1fd9d99f48cd8cf59630e0ff60f67d4ed2ec4e5e7475970449a6c06329009ee0ce2567892587675781a31e4bb2774403b2f78e9811df2cb397fa602572266747704c6258077910902eb7420bcb4ab743d1610cddba9019e7867aaad3aa7ba9b04968064a409b66733f9f78c566a25ff478cba37a2ffe23203d4b05bceef826f174b0be7912d19432cc759325251fa094d70693fb672d6f9e799284081b3adb541dd8f27ef80dcf1e7f0ff30f2fd976659457ce41e175a2d6301b777981ccc16b9a8247abaab8de0867836c27de0146fe4d0e1fd39b86ba51f0b58601cfcbd7f6f3451fe4184b26ed44ac2f6f7bb4ce5d9a80f88c2cbfe7553e5ab97c8b028ae16b4f70f037753b8c229a6e5e9038fcbb9b4c2abb954894f8f2faf177bfdaab3b0ed537156633621d16b62d58ba4ebe518997c33e2304976ba6af9df7e7e34302c7910ae559c7e3d20a30d71c14f85c0e86f26291bbf18c2d9dfe9a908592eea4523e6c1e5d9bb5abfbebfccd5c4e136f9be777723e932b06c029df5125191000c90fde62a8e5f8fceb28648f0c69ec3037d09302b2ade908a20dbd42761ca449b2743fc362649e16235769d9fbd7f87cd64972b58d69c0441abb5d22ddc6ed059f7ac1bdbfaef8c60e64631809c5e08c7cb4074c8ce6170d94b411604986be4ae163a'),
            })
            encrypted_payload = bytes.fromhex(encrypt_api(proto_data.hex()))
            
            headers_major = {
                "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
                "Accept-Encoding": "deflate, gzip", "X-GA-SV": "1789535859", "Authorization": "Bearer",
                "X-GA": "v1 1", "ReleaseVersion": "OB55", "Content-Type": "application/x-www-form-urlencoded",
                "X-Unity-Version": "2018.4.12f1", "Host": "loginbp.ppmainecoonghj.com"
            }
            session.post("https://loginbp.ppmainecoonghj.com/MajorRegister", headers=headers_major, data=encrypted_payload, verify=False, timeout=10)
            
            # تفعيل الحساب
            activation_data = login_guest(uid, password, region)
            if not activation_data: continue
            
            return {
                "account_id": activation_data["account_id"],
                "name": activation_data["nickname"],
                "password": password,
                "region": activation_data["region"],
                "status": "success",
                "uid": int(uid),
                "level": activation_data["level"],
                "exp": activation_data["exp"]
            }
        except Exception as e:
            time.sleep(0.3)
    return None

# ==========================================
# إعداد Flask (Vercel Entrypoint)
# ==========================================
app = Flask(__name__)

@app.route('/api/generate', methods=['GET'])
def generate():
    try:
        prefix = request.args.get('prefix', 'LAMIN')
        account = create_account("ME", prefix)
        
        if account:
            return jsonify([account])
        else:
            return jsonify({"error": "Failed to generate account after multiple attempts"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ملاحظة: Vercel يتعرف على المتغير `app` تلقائياً
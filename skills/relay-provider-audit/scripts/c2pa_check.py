"""读 mp4 的 C2PA 内容凭证并校验签名 / 文件哈希：BytePlus 方舟原片带 BytePlus_ModelArk 签名的 c2pa.created 动作（model_name、log_id、时间）。
用法：uv run --with c2pa-python python -I c2pa_check.py <mp4>…   结果另存 <mp4>.c2pa.json"""
import c2pa, json, sys
for f in sys.argv[1:]:
    j = json.loads(c2pa.Reader(f).json()); open(f + ".c2pa.json", "w").write(json.dumps(j, ensure_ascii=False, indent=1))
    m = j["manifests"][j["active_manifest"]]
    acts = [a for x in m["assertions"] if x["label"].startswith("c2pa.actions") for a in x["data"]["actions"]]
    ok = [r["code"] for r in j["validation_results"]["activeManifest"]["success"]]
    bad = [r["code"] for r in j["validation_results"]["activeManifest"]["failure"]]
    print(f, "| 签发", m["signature_info"]["issuer"], "|", [(a["action"], a.get("parameters", {}).get("model_name"), a.get("parameters", {}).get("log_id"), a.get("when")) for a in acts],
          "| 签名", "claimSignature.validated" in ok, "| 文件哈希", "assertion.bmffHash.match" in ok, "| 失败项", bad)

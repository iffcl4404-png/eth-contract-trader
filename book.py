import urllib.request, json
p = urllib.request.ProxyHandler({"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"})
o = urllib.request.build_opener(p)
r = urllib.request.Request("https://www.okx.com/api/v5/market/books?instId=ETH-USDT-SWAP&sz=12", headers={"User-Agent": "Mozilla/5.0"})
d = json.loads(o.open(r, timeout=10).read())
asks = d["data"][0]["asks"][:8]
bids = d["data"][0]["bids"][:8]
print("卖墙(阻力):")
for a in reversed(asks):
    print(f"  {a[0]:>10}  x {a[1]} 张")
print("--- 现价 ---")
print("买墙(支撑):")
for b in bids:
    print(f"  {b[0]:>10}  x {b[1]} 张")

import requests
B="http://127.0.0.1:8000"
s=requests.Session(); s.verify=False
for p,a in [("/api/health",False),("/api/auth/me",True),("/api/tm1/dimensions",True),("/api/paw/status",True)]:
 r=s.get(B+p,timeout=10); ok=r.status_code==200 or (a and r.status_code==401); print(p,r.status_code,"OK" if ok else "FAIL")
r=s.get(B+"/",timeout=5); print("GET /",r.status_code)

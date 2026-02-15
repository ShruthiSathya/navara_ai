"""
Run this directly: python3 debug_dgidb_now.py
It introspects DrugConnection then tries every access pattern.
"""
import asyncio, ssl, certifi

try:
    import aiohttp
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp", "certifi", "-q"])
    import aiohttp


async def main():
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    conn = aiohttp.TCPConnector(ssl=ssl_ctx)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:

        async def gql(q, v=None):
            body = {"query": q}
            if v:
                body["variables"] = v
            async with session.post(
                "https://dgidb.org/api/graphql",
                json=body,
                headers={"Content-Type": "application/json"},
            ) as r:
                return r.status, await r.json()

        # ── 1. What fields does DrugConnection have? ─────────────────────────
        print("\n─── DrugConnection fields ───")
        _, d = await gql('{ __type(name:"DrugConnection"){ fields{ name } } }')
        dc_fields = [f["name"] for f in (d.get("data",{}).get("__type",{}) or {}).get("fields",[])]
        print("  ", dc_fields)

        # ── 2. What fields does DrugEdge have? ───────────────────────────────
        print("─── DrugEdge fields ───")
        _, d = await gql('{ __type(name:"DrugEdge"){ fields{ name } } }')
        de_fields = [f["name"] for f in (d.get("data",{}).get("__type",{}) or {}).get("fields",[])]
        print("  ", de_fields)

        # ── 3. Try every plausible pattern ───────────────────────────────────
        names = ["NILOTINIB", "IMATINIB"]
        patterns = {
            "nodes":              "{ drugs(names:$n){ nodes{ name interactions{ gene{ name } } } } }",
            "edges.node":         "{ drugs(names:$n){ edges{ node{ name interactions{ gene{ name } } } } } }",
            "direct (no wrap)":   "{ drugs(names:$n){ name interactions{ gene{ name } } } }",
        }

        # Also probe the return type of drugs() to confirm
        print("─── drugs() return type ───")
        _, d = await gql('{ __schema{ queryType{ fields{ name type{ name kind ofType{ name kind } } } } } }')
        qtfields = d.get("data",{}).get("__schema",{}).get("queryType",{}).get("fields",[]) or []
        dfield = next((f for f in qtfields if f["name"]=="drugs"), None)
        if dfield:
            t = dfield["type"]
            print(f"  drugs() returns: kind={t['kind']} name={t['name']} ofType={t.get('ofType')}")

        print("\n─── Trying access patterns ───")
        for label, q in patterns.items():
            full_q = "query Q($n:[String!]!) " + q
            status, data = await gql(full_q, {"n": names})
            if "errors" in data:
                msgs = [e["message"] for e in data["errors"]]
                print(f"  ✗ {label}: {msgs[0]}")
            else:
                print(f"  ✓ {label}: SUCCESS")
                # Show a sample
                raw = data.get("data",{}).get("drugs",{})
                print(f"    raw keys: {list(raw.keys()) if isinstance(raw, dict) else type(raw)}")
                break

        print("\nDone. Use the ✓ pattern above in data_fetcher.py\n")


asyncio.run(main())
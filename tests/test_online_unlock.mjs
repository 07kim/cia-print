import assert from "node:assert/strict";
import handler from "../api/unlock.js";

function request(password) {
  return { method: "POST", body: { password } };
}

function response() {
  return {
    statusCode: 0,
    headers: {},
    body: null,
    setHeader(name, value) { this.headers[name] = value; },
    status(code) { this.statusCode = code; return this; },
    json(value) { this.body = value; return this; },
  };
}

{
  const res = response();
  handler(request("admin0000"), res);
  assert.equal(res.statusCode, 200);
  assert.deepEqual(res.body, { ok: true, admin: true });
  assert.equal(res.body.token, undefined);
}

{
  const res = response();
  handler(request("PRINT"), res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.ok, true);
  assert.equal(typeof res.body.token, "string");
}

{
  const res = response();
  handler(request("wrong"), res);
  assert.equal(res.statusCode, 401);
}

console.log("online unlock tests passed");

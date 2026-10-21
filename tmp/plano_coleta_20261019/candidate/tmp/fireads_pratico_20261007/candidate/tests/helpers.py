import json


class FakeCursor:
    def __init__(self, fetchone_result=None, fetchall_result=None, rowcount=1):
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []
        self.rowcount = rowcount
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result


class FakeConn:
    def __init__(self, cursor=None):
        self.cursor_obj = cursor or FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class FakeRequest:
    def __init__(
        self,
        body,
        content_type="application/json",
        headers=None,
        method="POST",
        path="/webhook",
    ):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")

        self.body = body
        self.content_type = content_type
        self.headers = headers or {"Content-Length": str(len(body))}
        self.method = method
        self.path = path


def json_response_payload(response):
    return json.loads(response.content.decode("utf-8"))

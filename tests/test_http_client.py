from pipeline.http_client import USER_AGENT, make_session


def test_session_sends_user_agent():
    session = make_session()
    assert session.headers["User-Agent"] == USER_AGENT

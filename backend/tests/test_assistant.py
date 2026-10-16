"""Ask FieldDx: retrieval finds the right fields, and with no model it answers from the records alone."""
from app import assistant


def test_a_field_named_in_the_question_is_retrieved_first():
    docs = assistant.retrieve("niphad", "What is wrong with field 94?")
    assert docs[0].id == "F094"
    assert any(d.id == "area" for d in docs)


def test_the_open_case_comes_first_with_its_evidence():
    docs = assistant.retrieve("niphad", "Why is it ranked this way?", case_id="F128")
    assert docs[0].id == "F128"
    assert "Evidence:" in docs[0].text and "E1 " in docs[0].text


def test_follow_up_questions_keep_the_field_from_the_last_turn():
    history = [{"role": "user", "text": "Tell me about plot 146"}, {"role": "assistant", "text": "Field 146 ..."}]
    docs = assistant.retrieve("niphad", "What should I check there first?", history=history)
    assert docs[0].id == "F146"


def test_without_a_model_the_answer_is_the_record_itself(client):
    r = client.post("/api/ask", json={"question": "What is happening in field 128?"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "retrieval"
    assert "Field 128" in body["answer"]
    assert body["sources"][0]["id"] == "F128" and body["sources"][0]["link"] == "/case/F128"


def test_asking_about_a_case_outside_the_area_is_refused(client):
    assert client.post("/api/ask", json={"question": "hi", "case_id": "X999"}).status_code == 404

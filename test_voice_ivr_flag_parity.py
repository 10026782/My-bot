import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-voice-ivr-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:VOICE_IVR_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patVoiceIvrTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appVoiceIvrTest")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app


_FORM = {
    "CallSid": "CA-voice-ivr-test",
    "From": "+972500000000",
    "To": "+972511111111",
    "Digits": "1",
}


def _post(path, enabled):
    with patch.object(app, "_validate_twilio_signature", return_value=True), \
         patch("feature_flags.is_enabled", return_value=enabled), \
         patch("voice_adapter.process_voice_step", return_value="<Response><Say>ok</Say></Response>") as process:
        response = app.app.test_client().post(path, data=_FORM)
    return response, process


def test_voice_routes_flag_off_do_not_continue_ivr():
    for path in ("/voice/incoming", "/voice/step"):
        response, process = _post(path, False)
        assert response.status_code == 200
        assert "השירות לא פעיל." in response.get_data(as_text=True)
        process.assert_not_called()


def test_voice_routes_flag_on_continue_ivr():
    for path in ("/voice/incoming", "/voice/step"):
        response, process = _post(path, True)
        assert response.status_code == 200
        assert response.get_data(as_text=True) == "<Response><Say>ok</Say></Response>"
        process.assert_called_once()

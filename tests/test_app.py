import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from app import create_app
from backend.ai_service import answer_question
from backend.eligibility_engine import assess_eligibility


ROOT = Path(__file__).resolve().parents[1]


class JanSahayakApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")

    def test_unavailable_live_integrations_are_not_exposed(self):
        self.assertEqual(self.client.get("/api/alerts").status_code, 404)
        self.assertEqual(
            self.client.post("/api/offices/search", json={"location": "Lucknow"}).status_code,
            404,
        )

    def test_scheme_search_and_trailing_slash(self):
        response = self.client.get("/api/schemes?q=scholarship")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 2)
        self.assertEqual(response.json["schemes"][0]["scheme_slug"], "post-matric-scholarship-sc")
        self.assertEqual(self.client.get("/api/schemes/").status_code, 200)

    def test_scheme_search_finds_related_result_with_typos_and_state_name(self):
        response = self.client.get("/api/schemes?q=UP%20scholership")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 2)
        self.assertEqual(response.json["schemes"][0]["scheme_slug"], "post-matric-scholarship-sc")
        self.assertEqual(response.json["schemes"][1]["scheme_slug"], "pm-yasasvi-schools")

    def test_seed_catalogue_has_at_least_ten_partial_source_linked_schemes(self):
        response = self.client.get("/api/schemes")
        self.assertGreaterEqual(response.json["count"], 10)
        self.assertTrue(
            all(
                scheme["verification_status"] in {"verified", "partial", "unverified"}
                and scheme["official_source_url"].startswith("https://")
                for scheme in response.json["schemes"]
            )
        )

    def test_beneficiary_filter(self):
        response = self.client.get("/api/schemes?target=Farmers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 1)
        self.assertEqual(response.json["schemes"][0]["scheme_slug"], "pm-kisan")

    def test_filter_metadata_endpoint(self):
        response = self.client.get("/api/filters")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Central", response.json["government_levels"])
        self.assertEqual(response.json["states"], [])

    def test_hindi_scheme_search_returns_localized_beneficiary_text(self):
        response = self.client.get("/api/schemes?q=%E0%A4%9B%E0%A4%BE%E0%A4%A4%E0%A5%8D%E0%A4%B0%E0%A4%B5%E0%A5%83%E0%A4%A4%E0%A5%8D%E0%A4%A4%E0%A4%BF")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 2)
        self.assertTrue(
            any("अनुसूचित जाति" in scheme["target_beneficiaries_hi"] for scheme in response.json["schemes"])
        )

    def test_scheme_detail_and_unknown_scheme(self):
        response = self.client.get("/api/schemes/pm-kisan")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["scheme"]["scheme_name"], "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)")
        self.assertIn("किसान", response.json["scheme"]["target_beneficiaries_hi"])
        self.assertEqual(self.client.get("/api/schemes/not-a-scheme").status_code, 404)

    def test_scheme_comparison_validates_and_returns_requested_schemes(self):
        response = self.client.get(
            "/api/schemes/compare?slug=pm-kisan&slug=post-matric-scholarship-sc"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["schemes"]), 2)
        self.assertEqual(self.client.get("/api/schemes/compare?slug=pm-kisan").status_code, 400)

    def test_eligibility_endpoint_does_not_claim_approval_for_partial_data(self):
        response = self.client.post(
            "/api/eligibility/check",
            json={
                "scheme_slug": "post-matric-scholarship-sc",
                "answers": {
                    "social_category": "SC",
                    "study_stage": "post-matric",
                    "study_country": "India",
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["overall_status"], "needs_more_information")
        self.assertTrue(all(item["status"] == "meets" for item in response.json["conditions"]))

    def test_eligibility_endpoint_distinguishes_failures_and_missing_answers(self):
        response = self.client.post(
            "/api/eligibility/check",
            json={
                "scheme_slug": "post-matric-scholarship-sc",
                "answers": {"social_category": "General"},
            },
        )
        statuses = [item["status"] for item in response.json["conditions"]]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(statuses, ["does_not_meet", "unknown", "unknown"])

    def test_invalid_eligibility_requests(self):
        self.assertEqual(self.client.post("/api/eligibility/check", json=[]).status_code, 400)
        self.assertEqual(self.client.post("/api/eligibility/check", json={}).status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/eligibility/check", json={"scheme_slug": "missing", "answers": {}}
            ).status_code,
            404,
        )

    def test_invalid_and_unknown_chat_requests(self):
        self.assertEqual(self.client.post("/api/chat", json={"message": " "}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/chat", json={"message": "x" * 1201}).status_code, 400
        )
        response = self.client.post("/api/chat", json={"message": "Tell me about marine fishing"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("couldn't find", response.json["answer"])
        self.assertEqual(response.json["schemes"], [])

    def test_chat_uses_hindi_catalogue_answers(self):
        response = self.client.post(
            "/api/chat",
            json={"message": "यूपी छात्रवृत्ति के बारे में बताइए", "language": "hi"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mode"], "rule-based")
        self.assertIn("उत्तर प्रदेश-विशिष्ट", response.json["answer"])
        self.assertIn("Post-Matric Scholarship", response.json["answer"])

    def test_complaint_draft_is_validated_and_not_submitted(self):
        response = self.client.post(
            "/api/complaints/generate",
            json={"message": "मेरी छात्रवृत्ति का भुगतान नहीं आया।", "language": "hi"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("छात्रवृत्ति", response.json["draft"])
        self.assertIn("शैक्षणिक सत्र", response.json["clarifying_questions"][0])
        self.assertFalse(response.json["submitted"])
        self.assertIsNone(response.json["channel"])
        self.assertEqual(self.client.post("/api/complaints/generate", json={}).status_code, 400)

    def test_fraud_check_uses_heuristics_and_warns_about_sensitive_requests(self):
        official = self.client.post(
            "/api/fraud/check", json={"url": "https://socialjustice.gov.in/schemes/25"}
        )
        suspicious = self.client.post(
            "/api/fraud/check",
            json={"url": "http://bit.ly/claim", "message": "Send your OTP and fee"},
        )
        self.assertEqual(official.json["category"], "Verified Official")
        self.assertIn("does not open", official.json["notice"])
        self.assertEqual(suspicious.json["category"], "Suspicious")
        self.assertEqual(self.client.post("/api/fraud/check", json={}).status_code, 400)

    def test_document_analyzer_validates_type_and_does_not_store_upload(self):
        valid = self.client.post(
            "/api/documents/analyze",
            data={"file": (io.BytesIO(b"%PDF-1.7\nsample"), "certificate.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json["analysis"]["storage"], "not_saved")
        self.assertEqual(valid.json["analysis"]["text_extraction"], "unavailable")
        invalid = self.client.post(
            "/api/documents/analyze",
            data={"file": (io.BytesIO(b"not a pdf"), "certificate.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(invalid.status_code, 400)

    def test_live_scheme_source_returns_live_text_without_marking_scheme_verified(self):
        from backend.live_sources import check_scheme_source

        live_page = {
            "scheme_slug": "pm-kisan",
            "scheme_name": "PM-KISAN",
            "source_url": "https://pmkisan.gov.in/",
            "source_status": "reachable",
            "page_title": "Official scheme page",
            "excerpt": "Official page text.",
            "checked_at": "2026-11-06T00:00:00+00:00",
            "cached": False,
            "notice": "Text only.",
        }
        with patch("app.check_scheme_source", return_value=live_page):
            response = self.client.get("/api/schemes/pm-kisan/source")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["excerpt"], "Official page text.")
        scheme = self.client.get("/api/schemes/pm-kisan").json["scheme"]
        self.assertEqual(scheme["verification_status"], "partial")

    def test_live_scheme_source_extracts_page_text_without_script_content(self):
        from backend.live_sources import _extract

        title, text = _extract(
            "<html><title>Official page</title><script>hidden secret</script>"
            "<body><h1>Scheme notice</h1><p>Current public text.</p></body></html>"
        )
        self.assertEqual(title, "Official page")
        self.assertIn("Current public text.", text)
        self.assertNotIn("hidden secret", text)

    def test_application_tracker_is_profile_scoped_and_records_history(self):
        profile_id = "0ea1d0d5-950a-49e9-8718-71f44648bd22"
        headers = {"X-Profile-Id": profile_id}
        self.assertEqual(self.client.get("/api/applications").status_code, 400)
        created = self.client.post(
            "/api/applications",
            headers=headers,
            json={"scheme_slug": "pm-kisan"},
        )
        self.assertEqual(created.status_code, 201)
        application = created.json["application"]
        updated = self.client.post(
            "/api/applications",
            headers=headers,
            json={
                "application_id": application["id"],
                "status": "Under Verification",
            },
        )
        self.assertEqual(updated.status_code, 201)
        self.assertEqual(len(updated.json["application"]["history"]), 2)
        self.assertEqual(
            self.client.get(
                "/api/applications",
                headers={"X-Profile-Id": "a4323d00-eddf-4519-8aa9-1e32f0d7b6f1"},
            ).json["applications"],
            [],
        )
        self.assertEqual(
            self.client.post(
                "/api/applications",
                headers=headers,
                json={"scheme_slug": "pm-kisan", "status": "Maybe Approved"},
            ).status_code,
            400,
        )

    def test_hindi_query_uses_local_rule_based_retrieval(self):
        response = self.client.post(
            "/api/chat", json={"message": "Mujhe scholarship chahiye", "language": "hi"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mode"], "rule-based")
        self.assertEqual(response.json["schemes"][0]["scheme_slug"], "post-matric-scholarship-sc")
        self.assertIn("आधिकारिक", response.json["answer"])
        self.assertIn("अनुसूचित जाति", response.json["answer"])

    def test_devanagari_query_uses_local_scheme_retrieval(self):
        response = self.client.post(
            "/api/chat", json={"message": "मुझे छात्रवृत्ति चाहिए", "language": "hi"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mode"], "rule-based")
        self.assertIn(
            "post-matric-scholarship-sc",
            [scheme["scheme_slug"] for scheme in response.json["schemes"]],
        )

    def test_up_scholarship_typo_recommends_related_scheme_without_claiming_up_scope(self):
        response = self.client.post(
            "/api/chat",
            json={"message": "UP scholership ke bare me jankari do", "language": "hi"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["schemes"][0]["scheme_slug"],
            "post-matric-scholarship-sc",
        )
        self.assertIn("उत्तर प्रदेश-विशिष्ट योजना की पुष्टि नहीं है", response.json["answer"])
        self.assertIn("मिलते-जुलते विषय की सिफारिशें", response.json["answer"])
        self.assertIn("अनुसूचित जाति", response.json["answer"])

    def test_document_question_asks_for_scheme_or_reports_missing_source_data(self):
        generic = self.client.post(
            "/api/chat", json={"message": "कौन से दस्तावेज़ चाहिए?", "language": "hi"}
        )
        specific = self.client.post(
            "/api/chat",
            json={"message": "इस छात्रवृत्ति के दस्तावेज़ क्या हैं?", "language": "hi"},
        )
        self.assertIn("किस योजना", generic.json["answer"])
        self.assertIn(
            "post-matric-scholarship-sc",
            [scheme["scheme_slug"] for scheme in specific.json["schemes"]],
        )
        self.assertIn("दस्तावेज़ों की सूची", specific.json["answer"])

    def test_source_urls_and_verification_labels_are_explicit(self):
        seed = json.loads((ROOT / "data" / "schemes.json").read_text(encoding="utf-8"))
        for scheme in seed:
            parsed = urlparse(scheme["official_source_url"])
            self.assertEqual(parsed.scheme, "https")
            self.assertTrue(parsed.netloc)
            self.assertIn(scheme["verification_status"], {"verified", "partial", "unverified"})
            self.assertTrue(scheme["last_verified_date"])


class EligibilityEngineTests(unittest.TestCase):
    def setUp(self):
        self.scheme = {
            "id": 1,
            "scheme_slug": "test",
            "verification_status": "verified",
            "eligibility_rules": [
                {
                    "key": "age",
                    "name": "Age range",
                    "operator": "gte",
                    "value": 18,
                    "pass_explanation": "Age meets the recorded minimum.",
                    "fail_explanation": "Age is below the recorded minimum.",
                },
                {
                    "key": "resident",
                    "name": "Residence",
                    "operator": "equals",
                    "value": "India",
                    "pass_explanation": "Residence matches the recorded condition.",
                    "fail_explanation": "Residence does not match the recorded condition.",
                },
            ],
        }

    def test_meets_all_recorded_conditions(self):
        result = assess_eligibility(self.scheme, {"age": 20, "resident": "India"})
        self.assertEqual(result["overall_status"], "meets_recorded_conditions")

    def test_fails_one_recorded_condition(self):
        result = assess_eligibility(self.scheme, {"age": 17, "resident": "India"})
        self.assertEqual(result["overall_status"], "does_not_meet_recorded_conditions")

    def test_missing_information_is_unknown(self):
        result = assess_eligibility(self.scheme, {"age": 20})
        self.assertEqual(result["conditions"][1]["status"], "unknown")
        self.assertEqual(result["overall_status"], "needs_more_information")


if __name__ == "__main__":
    unittest.main()

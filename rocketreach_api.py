"""RocketReach API integration for contact lookup."""

import requests
import config


class RocketReachAPI:
    """Client for RocketReach API to look up business contacts."""

    BASE_URL = "https://api.rocketreach.co/v2"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.ROCKETREACH_API_KEY
        if not self.api_key:
            raise ValueError("RocketReach API key required. Set ROCKETREACH_API_KEY in .env file.")
        self.headers = {
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def search_company(self, company_name: str, location: str = "Miami, FL") -> dict:
        """Search for a company by name and location."""
        url = f"{self.BASE_URL}/api/search"
        payload = {
            "query": {
                "company_name": [company_name],
                "location": [location]
            },
            "start": 1,
            "page_size": 5
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    def lookup_person(self, person_id: int) -> dict:
        """Look up detailed contact info for a person by their ID."""
        url = f"{self.BASE_URL}/api/person/lookup"
        payload = {"id": person_id}

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    def search_person_by_company(self, company_name: str, title_keywords: list = None) -> dict:
        """Search for people at a company, optionally filtering by title."""
        url = f"{self.BASE_URL}/api/search"

        query = {
            "current_employer": [company_name]
        }

        # Look for owners, managers, or decision makers
        if title_keywords is None:
            title_keywords = ["owner", "manager", "director", "president", "ceo", "founder"]

        query["current_title"] = title_keywords

        payload = {
            "query": query,
            "start": 1,
            "page_size": 10
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    def get_contact_info(self, business_name: str, address: str = None) -> dict:
        """
        Get contact information for a business.
        Returns owner/manager details with emails and phone numbers.
        """
        result = {
            "business_name": business_name,
            "contacts": [],
            "error": None
        }

        # Search for people at the company
        search_result = self.search_person_by_company(business_name)

        if "error" in search_result:
            result["error"] = search_result["error"]
            return result

        profiles = search_result.get("profiles", [])

        for profile in profiles[:3]:  # Get top 3 contacts
            contact = {
                "name": profile.get("name", ""),
                "title": profile.get("current_title", ""),
                "email": None,
                "phone": None,
                "linkedin": profile.get("linkedin_url", ""),
                "profile_id": profile.get("id")
            }

            # Get detailed info with email/phone if available
            if profile.get("id"):
                details = self.lookup_person(profile["id"])
                if "error" not in details:
                    emails = details.get("emails", [])
                    phones = details.get("phones", [])

                    if emails:
                        contact["email"] = emails[0].get("email")
                    if phones:
                        contact["phone"] = phones[0].get("number")

            result["contacts"].append(contact)

        return result

    def check_api_status(self) -> dict:
        """Check API key validity and remaining credits."""
        url = f"{self.BASE_URL}/api/account"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e), "valid": False}


def test_api():
    """Test the RocketReach API connection."""
    try:
        api = RocketReachAPI()
        print("Testing RocketReach API connection...")

        status = api.check_api_status()
        if "error" in status:
            print(f"API Error: {status['error']}")
            return False

        print(f"API Status: Connected")
        print(f"Account: {status}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    test_api()

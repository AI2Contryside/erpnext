"""
ERPNext API 基础客户端
所有请求自动添加 X-Tenant-ID Header
"""

import requests
import json
from typing import Optional, Dict, Any, List


class ERPNextClient:
    """ERPNext REST API 客户端"""

    def __init__(self, url: str, api_key: str, api_secret: str, tenant_id: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.tenant_id = tenant_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {api_key}:{api_secret}",
            "Content-Type": "application/json",
            "X-Tenant-ID": tenant_id
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise Exception(f"API Error {response.status_code}: {response.text}")
        return response.json() if response.content else {}

    def get_list(self, doctype: str, filters: Optional[Dict] = None,
                 fields: Optional[List[str]] = None, limit: int = 20,
                 offset: int = 0, order_by: str = "modified desc") -> List[Dict]:
        params = {
            "filters": json.dumps(filters or []),
            "fields": json.dumps(fields) if fields else json.dumps(["*"]),
            "limit": limit, "offset": offset, "order_by": order_by
        }
        result = self._make_request("GET", f"/api/resource/{doctype}", params=params)
        return result.get("data", [])

    def get_doc(self, doctype: str, name: str) -> Dict:
        result = self._make_request("GET", f"/api/resource/{doctype}/{name}")
        return result.get("data", {})

    def insert(self, data: Dict) -> Dict:
        result = self._make_request("POST", f"/api/resource/{data['doctype']}", json=data)
        return result.get("data", {})

    def update(self, doctype: str, name: str, data: Dict) -> Dict:
        result = self._make_request("PUT", f"/api/resource/{doctype}/{name}", json=data)
        return result.get("data", {})

    def delete(self, doctype: str, name: str) -> bool:
        self._make_request("DELETE", f"/api/resource/{doctype}/{name}")
        return True

    def call_method(self, doctype: str, name: str, method: str, **kwargs) -> Any:
        result = self._make_request("POST", f"/api/method/{doctype}.{method}",
                                   params={"name": name, **kwargs})
        return result.get("message", {})

    def get_count(self, doctype: str, filters: Optional[Dict] = None) -> int:
        params = {"filters": json.dumps(filters or []), "doctype": doctype}
        result = self._make_request("GET", "/api/method/frappe.client.get_count", params=params)
        return result.get("message", 0)

    def exists(self, doctype: str, name: str) -> bool:
        try:
            self.get_doc(doctype, name)
            return True
        except Exception:
            return False

    def submit(self, doctype: str, name: str) -> Dict:
        return self.call_method(doctype, name, "submit")

    def cancel(self, doctype: str, name: str) -> Dict:
        return self.call_method(doctype, name, "cancel")


def create_client(config: Dict[str, str]) -> ERPNextClient:
    required = ["url", "api_key", "api_secret", "tenant_id"]
    for k in required:
        if k not in config:
            raise ValueError(f"Missing: {k}")
    return ERPNextClient(**config)

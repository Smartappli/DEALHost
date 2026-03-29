use reqwest::blocking::Client;
use reqwest::header::{ACCEPT, AUTHORIZATION};
use serde_json::{json, Value};

#[derive(Debug, Clone)]
pub struct DealHostClient {
    base_url: String,
    token: Option<String>,
    http: Client,
}

impl DealHostClient {
    pub fn new(base_url: impl Into<String>, token: Option<String>) -> Self {
        Self {
            base_url: base_url.into().trim_end_matches('/').to_string(),
            token,
            http: Client::new(),
        }
    }

    fn request(&self, method: reqwest::Method, path: &str, body: Option<Value>) -> Result<Value, reqwest::Error> {
        let mut req = self
            .http
            .request(method, format!("{}{}", self.base_url, path))
            .header(ACCEPT, "application/json");

        if let Some(token) = &self.token {
            req = req.header(AUTHORIZATION, format!("Bearer {}", token));
        }
        if let Some(payload) = body {
            req = req.json(&payload);
        }

        req.send()?.error_for_status()?.json::<Value>()
    }

    pub fn create_tool(
        &self,
        name: &str,
        slug: &str,
        description: &str,
        module_ids: Vec<i64>,
        enabled: bool,
    ) -> Result<Value, reqwest::Error> {
        self.request(
            reqwest::Method::POST,
            "/api/hosting/tools/",
            Some(json!({
                "name": name,
                "slug": slug,
                "description": description,
                "module_ids": module_ids,
                "enabled": enabled
            })),
        )
    }

    pub fn create_application(
        &self,
        name: &str,
        slug: &str,
        description: &str,
        module_ids: Vec<i64>,
        enabled: bool,
    ) -> Result<Value, reqwest::Error> {
        self.request(
            reqwest::Method::POST,
            "/api/hosting/applications/",
            Some(json!({
                "name": name,
                "slug": slug,
                "description": description,
                "module_ids": module_ids,
                "enabled": enabled
            })),
        )
    }
}

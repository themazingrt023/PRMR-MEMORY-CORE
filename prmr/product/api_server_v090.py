"""V0.90 deployable API entrypoint with verified Whop webhook intake."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

from prmr.product.api_config_v075 import PRMRAPIConfig, load_api_config
from prmr.product.api_server_v076 import create_app
from prmr.product.whop_manual_approval_v090 import WhopManualApprovalV090


def create_app_v090(config: PRMRAPIConfig | None = None):
    active_config = config or load_api_config()
    app = create_app(config=active_config)
    workflow = WhopManualApprovalV090(
        storage_path=Path(active_config.storage_path),
        expected_company_id=os.getenv("WHOP_EXPECTED_COMPANY_ID"),
        expected_product_id=os.getenv("WHOP_EXPECTED_PRODUCT_ID"),
    )
    app.state.whop_manual_approval_v090 = workflow

    @app.post("/v1/integrations/whop/webhook")
    async def whop_webhook(request: Request) -> JSONResponse:
        raw_body = await request.body()
        result = workflow.ingest(
            raw_body=raw_body,
            headers=dict(request.headers),
            webhook_secret=os.getenv("WHOP_WEBHOOK_SECRET"),
        )
        return JSONResponse(status_code=int(result["status_code"]), content=result)

    return app


app = create_app_v090()


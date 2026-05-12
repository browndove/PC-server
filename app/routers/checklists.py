from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/checklists", tags=["checklists"])

TEMPLATES: dict[str, dict] = {
    "pharmacy": {
        "type": "pharmacy",
        "version": 1,
        "title": "Pharmacy inspection checklist",
        "sections": [
            {
                "id": "part_iii",
                "title": "Part III — Checklist",
                "questions": [
                    {
                        "key": "pharmacy.sample",
                        "prompt": "Sample question (replace with Pharmacy Council items)",
                        "input": "boolean",
                        "required": False,
                    },
                ],
            },
        ],
    },
    "otc": {
        "type": "otc",
        "version": 1,
        "title": "OTC inspection checklist",
        "sections": [
            {
                "id": "part_iii",
                "title": "Part III — Checklist",
                "questions": [
                    {
                        "key": "otc.sample",
                        "prompt": "Sample question (replace with OTC programme items)",
                        "input": "boolean",
                        "required": False,
                    },
                ],
            },
        ],
    },
}


@router.get("/{type_name}", response_model=None)
async def get_checklist(type_name: str) -> dict | JSONResponse:
    key = type_name.lower()
    body = TEMPLATES.get(key)
    if not body:
        return JSONResponse(
            status_code=404,
            content={"error": "Unknown checklist type", "allowed": ["pharmacy", "otc"]},
        )
    return body

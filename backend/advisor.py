"""Claude-powered real estate advisor with smart context management.

Summary mode by default, full detail via tool call when Claude needs it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

log = logging.getLogger("advisor")

SYSTEM_PROMPT = """You are a senior Saudi real estate development advisor with deep expertise in:
- Riyadh land development, zoning regulations, and building codes
- Real estate fund structuring (CMA-regulated private funds)
- Construction cost estimation and project phasing
- Market positioning and comparable transaction analysis
- Risk assessment for development projects

You have access to:
- Parcel data from the Riyadh Geoportal (geometry, zoning, building code)
- Decoded building regulations (floors, FAR, setbacks, allowed uses)
- SREM market data (transaction volumes, price indices, trending districts)
- A complete financial pro-forma computed by a Python engine

CRITICAL RULES:
- NEVER perform mathematical calculations. All numbers come from the computation engine.
- If you need to suggest different scenarios, describe what parameters to change and the frontend will run the computation engine with those parameters.
- Focus on: market positioning, building program recommendations, risk factors, comparable developments, strategic advice.
- You can reference Arabic terms alongside English translations.
- When asked about competing projects or market conditions, reason from your training data and the SREM data provided.
- Currency is Saudi Riyal (SAR). All areas in square meters (m²).

When you need detailed pro-forma data (cost breakdowns, cash flows, sensitivity), call the get_proforma_detail tool."""

DETAIL_TOOL = {
    "name": "get_proforma_detail",
    "description": "Retrieve the full pro-forma detail including cost breakdowns, year-by-year cash flows, sensitivity analysis, and all fund fee items. Call this when you need specific numbers beyond the summary.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sections": {
                "type": "array",
                "items": {"type": "string", "enum": [
                    "land_costs", "construction_costs", "revenue",
                    "financing", "fund_fees", "fund_size",
                    "cash_flows", "sensitivity", "inputs_used",
                ]},
                "description": "Which sections of the pro-forma to retrieve.",
            },
        },
        "required": ["sections"],
    },
}


def _build_summary(
    land_object: dict,
    proforma: dict | None = None,
) -> str:
    """Build a compact summary (~2KB) for Claude's context."""
    parts = []

    # Parcel identity
    parts.append(f"""## Parcel Data
- Parcel ID: {land_object.get('parcel_id')}
- District: {land_object.get('district_name')}
- Municipality: {land_object.get('municipality')}
- Plan: {land_object.get('plan_number')}, Plot: {land_object.get('parcel_number')}
- Area: {land_object.get('area_sqm'):,.0f} m²""")

    # Zoning
    regs = land_object.get("regulations", {})
    parts.append(f"""## Zoning & Regulations
- Building Code: {land_object.get('building_code_label')}
- Primary Use: {land_object.get('primary_use_label')}
- Detailed Use: {land_object.get('detailed_use_label')}
- Max Floors: {regs.get('max_floors')}
- FAR: {regs.get('far')}
- Coverage Ratio: {regs.get('coverage_ratio')}
- Allowed Uses: {', '.join(regs.get('allowed_uses', []))}""")

    # Market
    mkt = land_object.get("market", {})
    parts.append(f"""## Market Data (SREM)
- Market Index: {mkt.get('srem_market_index', 'N/A')}
- Index Change: {mkt.get('srem_index_change', 'N/A')}
- Daily Transactions: {mkt.get('daily_total_transactions', 'N/A')}
- Daily Avg Price/m²: {mkt.get('daily_avg_price_sqm', 'N/A')} SAR""")

    # Pro-forma KPIs
    if proforma:
        kpis = proforma.get("kpis", {})
        fs = proforma.get("fund_size", {})
        rev = proforma.get("revenue", {})
        irr = kpis.get("irr")
        parts.append(f"""## Pro-Forma Summary
- Fund Size: {fs.get('total_fund_size', 0):,.0f} SAR
- Equity: {fs.get('equity_amount', 0):,.0f} SAR ({fs.get('equity_pct', 0):.0%})
- Bank Loan: {fs.get('bank_loan', 0):,.0f} SAR ({fs.get('debt_pct', 0):.0%})
- GBA: {proforma.get('construction_costs', {}).get('gba_sqm', 0):,.0f} m²
- Revenue: {rev.get('gross_revenue', 0):,.0f} SAR
- IRR: {irr:.2%} {'(negative)' if irr and irr < 0 else ''}
- ROE: {kpis.get('roe_total', 0):.1%}
- ROE Annualized: {kpis.get('roe_annualized', 0):.2%}
- Net Profit: {kpis.get('equity_net_profit', 0):,.0f} SAR
- Yield on Cost: {kpis.get('yield_on_cost', 0):.2f}x""")

    return "\n\n".join(parts)


def _extract_detail(proforma: dict, sections: list[str]) -> str:
    """Extract specific sections from the full pro-forma."""
    result = {}
    for section in sections:
        if section in proforma:
            result[section] = proforma[section]
    return json.dumps(result, ensure_ascii=False, indent=2)


async def get_advice(
    anthropic_client: AsyncAnthropic,
    land_object: dict,
    proforma: dict | None,
    question: str,
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, Any]:
    """Get strategic advice from Claude with smart context.

    Args:
        anthropic_client: Initialized AsyncAnthropic client.
        land_object: Land Object from data_fetch.
        proforma: Optional ProFormaResult from computation_engine.
        question: User's question.
        model: Claude model to use.

    Returns:
        {"response": str, "tool_calls_made": int}
    """
    summary = _build_summary(land_object, proforma)
    messages = [
        {"role": "user", "content": f"{summary}\n\n---\n\n**Question:** {question}"},
    ]

    tools = [DETAIL_TOOL] if proforma else []
    tool_calls = 0

    # Run conversation loop (Claude may call tools)
    while True:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await anthropic_client.messages.create(**kwargs)

        # Check if Claude wants to use a tool
        if response.stop_reason == "tool_use":
            tool_calls += 1
            # Find the tool use block
            for block in response.content:
                if block.type == "tool_use" and block.name == "get_proforma_detail":
                    sections = block.input.get("sections", [])
                    detail = _extract_detail(proforma, sections)
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": detail,
                        }],
                    })
                    break
            if tool_calls > 3:
                break  # safety limit
            continue

        # Extract text response
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        return {"response": text, "tool_calls_made": tool_calls}

    return {"response": "Unable to generate advice.", "tool_calls_made": tool_calls}


async def search_market(
    anthropic_client: AsyncAnthropic,
    land_object: dict,
    query: str,
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, Any]:
    """Market intelligence query using Claude with web search.

    Args:
        anthropic_client: Initialized AsyncAnthropic client.
        land_object: Land Object for context.
        query: User's search query.
        model: Claude model to use.

    Returns:
        {"response": str}
    """
    summary = _build_summary(land_object)
    messages = [
        {
            "role": "user",
            "content": (
                f"Context about the parcel:\n{summary}\n\n---\n\n"
                f"**Research Query:** {query}\n\n"
                f"Please research this query using your knowledge of the Saudi real estate market. "
                f"Include specific data points, comparable projects, and market trends where available. "
                f"Focus on the Riyadh market and the {land_object.get('district_name', 'target')} district area."
            ),
        },
    ]

    try:
        response = await anthropic_client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        return {"response": text}

    except Exception as exc:
        log.error("Search failed: %s", exc)
        return {"response": f"Search error: {exc}"}

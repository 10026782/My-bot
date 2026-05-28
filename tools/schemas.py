TOOL_SCHEMAS = [
    {"name":"add_knowledge","description":"הוספת עובדה לbusiness memory",
     "input_schema":{"type":"object","properties":{"fact":{"type":"string"}},"required":["fact"]}},
    {"name":"get_roi_report","description":"דוח ROI לפי מקור שיווק",
     "input_schema":{"type":"object","properties":{}}},
]

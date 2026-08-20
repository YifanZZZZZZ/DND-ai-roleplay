from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

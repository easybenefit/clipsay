"""Per-scene environment record."""

from pydantic import BaseModel, Field


class EnvironmentInScene(BaseModel):
    """The physical setting of a single scene — location, time, mood."""

    slugline: str = Field(
        description="A scene heading in industry-standard slugline form, indicating "
                    "location and time of day.",
        examples=["INT. COFFEE SHOP - NIGHT", "EXT. PARK - DAY"],
    )
    description: str = Field(
        description="A detailed description of the environment. No characters or actions "
                    "here — only the setting, lighting, and atmosphere.",
        examples=[
            "Warm yellow light glowed against the mottled brick wall while raindrops "
            "streaked the glass window with blurred neon reflections. Among the empty "
            "booths sat a lone half-finished iced latte; its foam collapsed, a faint "
            "lipstick mark on the rim. Beads of condensation gleamed on the stainless-"
            "steel espresso machine, and the record player's turntable rotated slowly "
            "in the shadows. A patch of wet floor shimmered with hazy reflected light.",
        ],
    )

    def __str__(self) -> str:
        return f"{self.slugline} -- {self.description}"

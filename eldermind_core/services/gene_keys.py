"""Gene Keys Hologenetic Profile module.

Gene Keys uses the same 64 hexagram wheel as Human Design. Each Gene Key is
1:1 with an HD gate, so we can derive the Hologenetic Profile directly from
the Personality and Design activations computed by the Human Design service.
"""

from typing import Final

# Mapping of Gene Keys spheres to their Human Design source.
# Sources verified against Richard Rudd's Golden Path Hologenetic Profile.
ACTIVATION_SEQUENCE: Final[dict[str, tuple[str, str]]] = {
    "Life's Work": ("personality", "Sun"),
    "Evolution": ("personality", "Earth"),
    "Radiance": ("design", "Sun"),
    "Purpose": ("design", "Earth"),
}

VENUS_SEQUENCE: Final[dict[str, tuple[str, str]]] = {
    "Purpose": ("design", "Earth"),
    "Attraction": ("design", "Moon"),
    "IQ": ("personality", "Venus"),
    "EQ": ("design", "Mars"),
    "SQ": ("design", "Venus"),
    "Core Wound": ("personality", "Mars"),
}

PEARL_SEQUENCE: Final[dict[str, tuple[str, str]]] = {
    "Vocation": ("personality", "Mars"),
    "Culture": ("design", "Jupiter"),
    "Brand": ("personality", "Sun"),
    "Pearl": ("personality", "Jupiter"),
}


def _find_activation(activations: list[dict], name: str) -> dict:
    """Return the activation matching the given body name."""
    for activation in activations:
        if activation["name"] == name:
            return activation
    raise ValueError(f"Activation for {name!r} not found in Human Design data")


def _build_sphere(
    sphere: str,
    sequence_name: str,
    source: tuple[str, str],
    hd_data: dict,
) -> dict:
    """Build a GeneKeySphere-like dictionary from an HD activation."""
    variant, body_name = source
    activation = _find_activation(hd_data[variant], body_name)
    return {
        "sphere": sphere,
        "sequence": sequence_name,
        "variant": variant.capitalize(),
        "body": body_name,
        "gene_key": activation["gate"],
        "gate": activation["gate"],
        "line": activation["line"],
        "longitude": activation["longitude"],
    }


def compute_gene_keys(human_design_data: dict) -> dict:
    """Derive the Gene Keys Hologenetic Profile from Human Design data.

    Args:
        human_design_data: Output dictionary from compute_human_design()
            containing "personality" and "design" activation lists.

    Returns:
        Dictionary with activation_sequence, venus_sequence and pearl_sequence
        mappings.
    """
    activation_sequence: dict[str, dict] = {}
    for sphere, source in ACTIVATION_SEQUENCE.items():
        activation_sequence[sphere] = _build_sphere(
            sphere=sphere,
            sequence_name="Activation",
            source=source,
            hd_data=human_design_data,
        )

    venus_sequence: dict[str, dict] = {}
    for sphere, source in VENUS_SEQUENCE.items():
        venus_sequence[sphere] = _build_sphere(
            sphere=sphere,
            sequence_name="Venus",
            source=source,
            hd_data=human_design_data,
        )

    pearl_sequence: dict[str, dict] = {}
    for sphere, source in PEARL_SEQUENCE.items():
        pearl_sequence[sphere] = _build_sphere(
            sphere=sphere,
            sequence_name="Pearl",
            source=source,
            hd_data=human_design_data,
        )

    return {
        "activation_sequence": activation_sequence,
        "venus_sequence": venus_sequence,
        "pearl_sequence": pearl_sequence,
    }

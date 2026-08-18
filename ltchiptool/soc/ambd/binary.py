# Copyright (c) Bl00d-B0b 2026-08-06.

from abc import ABC

from ltchiptool import SocInterface

from .util.models import (AMBD_BOOT_ADDRESS, AMBD_KM4_XIP_ADDRESS,
                          SectionHeader, pack_section)


class AmebaDBinary(SocInterface, ABC):
    """AmebaD image handling.

    The flash image set is km4_boot_all.bin (boot XIP+RAM sections) and
    km0_km4_image2.bin (KM0 image2 || KM4 image2, each of xip/ram/psram
    sections with 32-byte prepend headers, plain-concatenated when the
    security flags are off). The KM0 half and both boot images ship
    precompiled with the framework package; elf2bin here packages only the
    KM4 application image2 and concatenates the prebuilt KM0 half.
    """

    # The LibreTiny family builder (builder/family/realtek-ambd.py) packs the
    # OTA image from the linked ELF, so elf2bin/link2bin are not routed here
    # yet; the header primitives live in util/models.py.

    def elf2bin(self, input: str, ota_idx: int) -> dict:
        raise NotImplementedError(
            "AmebaD images are packed by the LibreTiny family builder"
        )

    def link2bin(self, input: str, ota_idx: int) -> dict:
        raise NotImplementedError(
            "AmebaD images are packed by the LibreTiny family builder"
        )

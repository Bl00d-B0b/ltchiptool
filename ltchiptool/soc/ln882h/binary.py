# Copyright (c) Etienne Le Cousin 2025-01-02.

from abc import ABC
from logging import warning
from os import stat
from os.path import dirname, isfile
from shutil import copyfile
from typing import List

from ltchiptool import SocInterface
from ltchiptool.util.fileio import chext, chname
from ltchiptool.util.fwbinary import FirmwareBinary

from .util import OTATOOL, MakeImageTool
from .util.models import PartDescInfo, part_type_str2num


class LN882hBinary(SocInterface, ABC):
    def elf2bin(self, input: str, ota_idx: int) -> List[FirmwareBinary]:
        toolchain = self.board.toolchain
        flash_layout = self.board["flash"]

        # find bootloader image
        input_boot = chname(input, "boot.bin")
        if not isfile(input_boot):
            raise FileNotFoundError("Bootloader image not found")

        # build output names
        output = FirmwareBinary(
            location=input,
            name="firmware",
            offset=0,
            title="Flash Image",
            description="Complete image with boot for flashing at offset 0",
            public=True,
        )
        out_boot = FirmwareBinary(
            location=input,
            name="boot",
            offset=self.board.region("boot")[0],
            title="Bootloader Image",
        )
        out_ptab = FirmwareBinary(
            location=input,
            name="part_table",
            offset=self.board.region("part_table")[0],
            title="Partition Table",
        )
        out_app = FirmwareBinary(
            location=input,
            name="app",
            offset=self.board.region("app")[0],
            title="Application Image",
            description="Firmware partition image for direct flashing",
            public=True,
        )
        out_ota = FirmwareBinary(
            location=input,
            name="ota",
            offset=self.board.region("ota")[0],
            title="OTA Image",
            description="Compressed App image for OTA flashing",
            public=True,
        )
        out_nvds = FirmwareBinary(
            location=input,
            name="ln_nvds",
            offset=self.board.region("ln_nvds")[0],
            title="NVDS (OTA flag)",
        )
        # print graph element
        output.graph(1)

        input_bin = chext(input, "bin")
        # objcopy ELF -> raw BIN
        toolchain.objcopy(input, input_bin)

        # Make Image Tool
        # fmt: off
        mkimage = MakeImageTool()
        mkimage.boot_filepath       = input_boot
        mkimage.app_filepath        = input_bin
        mkimage.flashimage_filepath = output.path
        mkimage.ver_str             = "1.0"
        mkimage.swd_crp             = 0
        mkimage.readPartCfg         = lambda : True
        # fmt: off

        # find all partitions
        for name, layout in flash_layout.items():
            (offset, _, length) = layout.partition("+")
            part_info = PartDescInfo(
                parttype = part_type_str2num(name.upper()),
                startaddr = int(offset, 16),
                partsize = int(length, 16)
            )
            mkimage._MakeImageTool__part_desc_info_list.append(part_info)

        if not mkimage.doAllWork():
            raise RuntimeError("MakeImageTool: Fail to generate image")

        # write all parts to files
        with out_boot.write() as f:
            f.write(mkimage._MakeImageTool__partbuf_bootram)
        with out_ptab.write() as f:
            f.write(mkimage._MakeImageTool__partbuf_parttab)
        with out_app.write() as f:
            f.write(mkimage._MakeImageTool__partbuf_app)

        # Make ota image
        ota_tool = OTATOOL()
        ota_tool.input_filepath = output.path
        ota_tool.output_dir     = dirname(input)
        if not ota_tool.doAllWork():
            raise RuntimeError("MakeImageTool: Fail to generate OTA image")

        # create a NVDS image indicating OTA download was successful
        #  - necessary when upgrading from LibreTiny v1.12.1, as partition layouts
        #    for several boards were changed in v1.13.0
        #  - changing the partition layout over-the-air requires flashing 'part_table',
        #    but applying OTA also requires a flag in `ln_nvds` to be set
        #  - because the running version of LT uses the old layout, it sets the flag in
        #    the wrong NVDS area
        with out_nvds.write() as f:
            nvds = b"NVDS[Ver 1.0]\x00" + b"\xff" * 6 + int.to_bytes(1, 4, "little")
            nvds = nvds + b"\xff" * (0x2000 - len(nvds))
            nvds = nvds + b"\xa5\xa5"  # indicate sector 1 is valid
            nvds = nvds + b"\xff" * (0x3000 - len(nvds))
            f.write(nvds)

        copyfile(ota_tool.output_filepath, out_ota.path)
        _, ota_size, _ = self.board.region("ota")
        if stat(out_ota.path).st_size > ota_size:
            warning(
                f"OTA size too large: {out_ota.filename} > {ota_size} (0x{ota_size:X})"
            )

        return output.group()

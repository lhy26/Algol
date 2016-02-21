#!/usr/bin/env python
# Copyright (c) 2015 Angel Terrones (<angelterrones@gmail.com>)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
from math import ceil
from math import log
import os.path
from myhdl import Signal
from myhdl import modbv
from myhdl import always_comb
from myhdl import always
from myhdl import instances
from myhdl import concat
from Core.memIO import MemOp
from Core.memIO import MemPortIO


class Memory:
    def __init__(self,
                 clk:          Signal,
                 rst:          Signal,
                 imem:         MemPortIO,
                 dmem:         MemPortIO,
                 SIZE:         int,
                 HEX:          str,
                 BYTES_X_LINE: int):
        assert SIZE >= 2**12, "Memory depth must be a positive number. Min value= 4 KB."
        assert not (SIZE & (SIZE - 1)), "Memory size must be a power of 2"
        assert type(BYTES_X_LINE) == int and BYTES_X_LINE > 0, "Number of bytes por line must be a positive number"
        assert not (BYTES_X_LINE & (BYTES_X_LINE - 1)), "Number of bytes por line must be a power of 2"
        assert type(HEX) == str and len(HEX) != 0, "Please, indicate a valid name for the bin file."
        assert os.path.isfile(HEX), "HEX file does not exist. Please, indicate a valid name"

        self.aw           = int(ceil(log(SIZE, 2)))
        self.bytes_x_line = BYTES_X_LINE
        self.clk          = clk
        self.rst          = rst
        self.imem         = imem
        self.dmem         = dmem
        self.i_data_o     = Signal(modbv(0)[32:])
        self.d_data_o     = Signal(modbv(0)[32:])
        self._memory      = [None for ii in range(0, 2**(self.aw - 2))]  # WORDS, no bytes
        self._imem_addr   = Signal(modbv(0)[30:])
        self._dmem_addr   = Signal(modbv(0)[30:])

        self.LoadMemory(SIZE, HEX)

    def LoadMemory(self, size_mem: int, bin_file: str):
        """
        Load a HEX file. The file have (2 * NBYTES + 1) por line.
        """
        n_lines = int(os.path.getsize(bin_file) / (2 * self.bytes_x_line + 1))  # calculate number of lines in the file
        bytes_file = n_lines * self.bytes_x_line
        assert bytes_file <= size_mem, "Error, HEX file is to big: {0} < {1}".format(size_mem, bytes_file)
        word_x_line = self.bytes_x_line >> 2

        with open(bin_file) as f:
            lines_f = [line.strip() for line in f]
            lines = [line[8 * i:8 * (i + 1)] for line in lines_f for i in range(word_x_line - 1, -1, -1)]

        for addr in range(size_mem >> 2):
            data = int(lines[addr], 16)
            self._memory[addr] = Signal(modbv(data)[32:])

    def GetRTL(self):
        @always(self.clk.posedge)
        def set_ready_signal():
            self.imem.ready.next = False if self.rst else self.imem.valid
            self.dmem.ready.next = False if self.rst else self.dmem.valid

        @always_comb
        def assignment_data_o():
            self.imem.rdata.next = self.i_data_o if self.imem.ready else 0xDEADF00D
            self.dmem.rdata.next = self.d_data_o if self.dmem.ready else 0xDEADF00D

        @always(self.clk.posedge)
        def set_fault():
            self.imem.fault.next = False
            self.dmem.fault.next = False

        @always_comb
        def assignment_addr():
            # This memory is addressed by word, not byte. Ignore the 2 LSB.
            self._imem_addr.next = self.imem.addr[self.aw:2]
            self._dmem_addr.next = self.dmem.addr[self.aw:2]

        @always(self.clk.posedge)
        def imem_rtl():
            self.i_data_o.next = self._memory[self._imem_addr]

            if self.imem.fcn == MemOp.M_WR:
                we                = self.imem.wr
                data              = self.imem.wdata
                self.i_data_o.next = self.imem.wdata
                self._memory[self._imem_addr].next = concat(data[8:0] if we[0] and self.imem.valid else self._memory[self._imem_addr][8:0],
                                                            data[16:8] if we[1] and self.imem.valid else self._memory[self._imem_addr][16:8],
                                                            data[24:16] if we[2] and self.imem.valid else self._memory[self._imem_addr][24:16],
                                                            data[32:24] if we[3] and self.imem.valid else self._memory[self._imem_addr][32:24])

        @always(self.clk.posedge)
        def dmem_rtl():
            self.d_data_o.next = self._memory[self._dmem_addr]

            if self.dmem.fcn == MemOp.M_WR:
                we                 = self.dmem.wr
                data               = self.dmem.wdata
                self.d_data_o.next = self.dmem.wdata
                self._memory[self._dmem_addr].next = concat(data[8:0] if we[0] and self.dmem.valid else self._memory[self._dmem_addr][8:0],
                                                            data[16:8] if we[1] and self.dmem.valid else self._memory[self._dmem_addr][16:8],
                                                            data[24:16] if we[2] and self.dmem.valid else self._memory[self._dmem_addr][24:16],
                                                            data[32:24] if we[3] and self.dmem.valid else self._memory[self._dmem_addr][32:24])

        return instances()

# Local Variables:
# flycheck-flake8-maximum-line-length: 200
# flycheck-flake8rc: ".flake8rc"
# End:

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

from myhdl import Signal
from myhdl import modbv
from myhdl import always_comb
from myhdl import concat
from myhdl import instances
from Core.consts import Consts


def IMMGen(sel,
           instruction,
           imm):
    """
    Generate the immediate values.

    :param sel:         Select the type of instruction/immediate
    :param instruction: Current instruction
    :param imm:         A 32-bit immediate value
    """
    sign   = Signal(False)
    b30_20 = Signal(modbv(0)[11:])
    b19_12 = Signal(modbv(0)[8:])
    b11    = Signal(False)
    b10_5  = Signal(modbv(0)[6:])
    b4_1   = Signal(modbv(0)[4:])
    b0     = Signal(False)

    @always_comb
    def _sign():
        sign.next     = False if sel == Consts.IMM_Z else instruction[31]

    @always_comb
    def rtl():
        b30_20.next   = instruction[31:20] if sel == Consts.IMM_U else concat(sign, sign, sign, sign, sign, sign, sign, sign, sign, sign, sign)
        b19_12.next   = instruction[20:12] if (sel == Consts.IMM_U or sel == Consts.IMM_UJ) else concat(sign, sign, sign, sign, sign, sign, sign, sign)
        b11.next      = (False if (sel == Consts.IMM_U or sel == Consts.IMM_Z) else
                         (instruction[20] if sel == Consts.IMM_UJ else
                          (instruction[7] if sel == Consts.IMM_SB else sign)))
        b10_5.next    = modbv(0)[6:] if (sel == Consts.IMM_U or sel == Consts.IMM_Z) else instruction[31:25]
        b4_1.next     = (modbv(0)[4:] if sel == Consts.IMM_U else
                         (instruction[12:8] if (sel == Consts.IMM_S or sel == Consts.IMM_SB) else
                          (instruction[20:16] if sel == Consts.IMM_Z else instruction[25:21])))
        b0.next       = (instruction[7] if sel == Consts.IMM_S else
                         (instruction[20] if sel == Consts.IMM_I else
                          (instruction[15] if sel == Consts.IMM_Z else False)))

    @always_comb
    def imm_concat():
        imm.next = concat(sign, b30_20, b19_12, b11, b10_5, b4_1, b0)

    return instances()

# Local Variables:
# flycheck-flake8-maximum-line-length: 200
# flycheck-flake8rc: ".flake8rc"
# End:

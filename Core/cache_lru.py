#!/usr/bin/env python
# ******************************************************************************
# This Source Code Form is subject to the terms of the
# Open Hardware Description License, v. 1.0. If a copy
# of the OHDL was not distributed with this file, You
# can obtain one at http:#juliusbaxter.net/ohdl/ohdl.txt
#
# Description: Data cache LRU implementation
#
# Copyright (C) 2012 Stefan Wallentowitz <stefan.wallentowitz@tum.de>
# Copyright (C) 2016 Angel Terrones <angelterrones@gmail.com>

from myhdl import always_comb
from myhdl import modbv
from myhdl import instances

# ******************************************************************************
# This module is taken from the mor1kx project (mri1kx_cache_lru.v file)
# ******************************************************************************
# This is the least-recently-used (LRU) calculation module. It
# essentially has two types of input and output. First, the history
# information needs to be evaluated to calculate the LRU value.
# Second, the current access and the LRU are one hot values of the
# ways.
#
# This module is pure combinational. All registering is done outside
# this module. The following parameter exists:
#
#  * NUMWAYS: Number of ways (must be greater than 1)
#
# The following ports exist:
#
#  * current: The current LRU history
#  * update: The new LRU history after access
#
#  * access: 0 if no access or one-hot of the way that accesses
#  * lru_pre: LRU before the access (one hot of ways)
#  * lru_post: LRU after the access (one hot of ways)
#
# The latter three have the width of NUMWAYS apparently. The first
# three are more complicated as this is an optimized way of storing
# the history information, which will be shortly described in the
# following.
#
# A naive approach to store the history of the access is to store the
# relative "age" of each element in a vector, for example for four
# ways:
#
#   0: 1 1: 3 2: 1 3:0
#
# This needs 4x2 bits, but more important it also needs a set of
# comparators and adders. This can become increasingly complex when
# using a higher number of cache ways with an impact on area and
# timing.
#
# Similarly, it is possible to store a "stack" of the access and
# reorder this stack on an access. But the problems are similar, it
# needs comparators etc.
#
# A neat approach is to store the history efficiently coded, while
# also easing the calculation. This approach stores the information
# whether each entry is older than the others. For example for the
# four-way example (x<y means x is older than y):
#
# |0<1|0<2|0<3|1<0|1<2|1<3|2<0|2<1|2<3|3<0|3<1|3<2|
#
# This is redundant as two entries can never be equally old meaning
# x<y == !y<x, leading to a simpler version
#
# |0<1|0<2|0<3|1<2|1<3|2<3|
#
# The calculations on this vector are much simpler and it is
# therefore used by this module.
#
# The width of this vector is the triangular number of (NUMWAYS-1),
# specifically:
#  WIDTH=NUMWAYS*(NUMWAYS-1)/2.
#
# The details of the algorithms are described below. The designer
# just needs to apply current history vector and the access and gets
# the updated history and the LRU before and after the access.
#
# Instantiation example:
# mor1kx_dcache_lru
#  (.NUMWAYS(4))
# u_lru(.current  (current_history[((NUMWAYS*(NUMWAYS-1))>>1)-1:0])),
#       .update   (updated_history[((NUMWAYS*(NUMWAYS-1))>>1)-1:0])),
#       .access   (access[NUMWAYS-1:0]),
#       .lru_pre  (lru_pre[NUMWAYS-1:0]),
#       .lru_post (lru_post[NUMWAYS-1:0]));
# ******************************************************************************


def CacheLRU(current,
             access,
             update,
             lru_pre,
             lru_post,
             NUMWAYS=2):

    # **************************************************************************
    # <    0      1      2      3
    # 0    1    (0<1)  (0<2)  (0<3)
    # 1  (1<0)    1    (1<2)  (1<3)
    # 2  (2<0)  (2<1)    1    (2<3)
    # 3  (3<0)  (3<1)  (3<2)    1
    #
    # As two entries can never be equally old (needs to be avoided on
    # the outside) this is equivalent to:
    #
    # <    0      1      2      3
    # 0    1    (0<1)  (0<2)  (0<3)
    # 1 !(0<1)    1    (1<2)  (1<3)
    # 2 !(0<2) !(1<2)    1    (2<3)
    # 3 !(0<3) !(1<3) !(2<3)    1
    #
    # The lower half below the diagonal is the inverted mirror of the
    # upper half. The number of entries in each half is of course
    # equal to the width of our LRU vector and the upper half is
    # filled with the values from the vector.
    #
    # The algorithm works as follows:
    #
    #  1. Fill the matrix (expand) with the values. The entry (i,i) is
    #     statically one.
    #
    #  2. The LRU_pre vector is the vector of the ANDs of the each row.
    #
    #  3. Update the values with the access vector (if any) in the
    #     following way: If access[i] is set, the values in row i are
    #     set to 0. Similarly, the values in column i are set to 1.
    #
    #  4. The update vector of the lru history is then generated by
    #     copying the upper half of the matrix back.
    #
    #  5. The LRU_post vector is the vector of the ANDs of each row.
    #
    # In the following an example will be used to demonstrate the algorithm:
    #
    #  NUMWAYS = 4
    #  current = 6'b110100;
    #  access  = 4'b0010;
    #
    # This current history is:
    #
    #  0<1 0<2 0<3 1<2 1<3 2<3
    #   0   0   1   0   1   1
    #
    # and way 2 is accessed.
    #
    # The history of accesses is 3>0>1>2 and the expected result is an
    # update to 2>3>0>1 with LRU_pre=2 and LRU_post=1
    # **************************************************************************

    if lru_post is not None:
        # Use the lru_post signal
        @always_comb
        def step_1():
            expand   = [modbv(0)[NUMWAYS:] for i in range(NUMWAYS)]
            offset = 0

            # 1. Fill the matrix (expand) with the values. The entry (i,i) is
            #    statically one.
            for i in range(0, NUMWAYS):
                expand[i][i] = True

                for j in range(i + 1, NUMWAYS):
                    expand[i][j] = current[offset + j - i - 1]
                for j in range(0, i):
                    expand[i][j] = not expand[j][i]

                offset = offset + NUMWAYS - i - 1

            # **********************************************************************
            # For the example expand is now:
            # <    0      1      2      3        0 1 2 3
            # 0    1    (0<1)  (0<2)  (0<3)    0 1 0 0 1
            # 1  (1<0)    1    (1<2)  (1<3) => 1 1 1 0 1
            # 2  (2<0)  (2<1)    1    (2<3)    2 1 1 1 1
            # 3  (3<0)  (3<1)  (3<2)    1      3 0 0 0 1
            # **********************************************************************

            # **********************************************************************
            #  2. The LRU_pre vector is the vector of the ANDs of the each
            #     row.
            # **********************************************************************
            tmp0 = modbv(0)[NUMWAYS:]
            for i in range(0, NUMWAYS):
                value = True
                for j in range(0, NUMWAYS):
                    value = value and expand[i][j]
                tmp0[i] = value
            lru_pre.next = tmp0

            # **********************************************************************
            # We derive why this is the case for the example here:
            # lru_pre[2] is high when the following condition holds:
            #
            #  (2<0) & (2<1) & (2<3).
            #
            # Applying the negation transform we get:
            #
            #  !(0<2) & !(1<2) & (2<3)
            #
            # and this is exactly row [2], so that here
            #
            # lru_pre[2] = &expand[2] = 1'b1;
            #
            # At this point you can also see why we initialize the diagonal
            # with 1.

            #  3. Update the values with the access vector (if any) in the
            #     following way: If access[i] is set, the values in row i
            #     are set to 0. Similarly, the values in column i are set
            #     to 1.
            # **********************************************************************
            for i in range(0, NUMWAYS):
                if access[i]:
                    for j in range(0, NUMWAYS):
                        if i != j:
                            expand[i][j] = False
                    for j in range(0, NUMWAYS):
                        if i != j:
                            expand[j][i] = True

            # **********************************************************************
            # Again this becomes obvious when you see what we do here.
            # Accessing way 2 leads means now
            #
            # (0<2) = (1<2) = (3<2) = 1, and
            # (2<0) = (2<1) = (2<3) = 0
            #
            # The matrix changes accordingly
            #
            #   0 1 2 3      0 1 2 3
            # 0 1 0 0 1    0 1 0 1 1
            # 1 1 1 0 1 => 1 1 1 1 1
            # 2 1 1 1 1    2 0 0 1 0
            # 3 0 0 0 1    3 0 0 1 1
            # **********************************************************************

            # **********************************************************************
            # 4. The update vector of the lru history is then generated by
            #    copying the upper half of the matrix back.
            # **********************************************************************
            offset = 0
            tmp1 = modbv(0)[len(update):]
            for i in range(0, NUMWAYS):
                for j in range(i + 1, NUMWAYS):
                    tmp1[offset + j - i - 1] = expand[i][j]
                offset = offset + NUMWAYS - i - 1
            update.next = tmp1

            # **********************************************************************
            # This is the opposite operation of step 1 and is clear now.
            # Update becomes:
            #
            #  update = 6'b011110
            #
            # This is translated to
            #
            #  0<1 0<2 0<3 1<2 1<3 2<3
            #   0   1   1   1   1   0
            #
            # which is: 2>3>0>1, which is what we expected.
            # **********************************************************************

            # **********************************************************************
            # 5. The LRU_post vector is the vector of the ANDs of each row.
            # **********************************************************************
            temp = modbv(0)[len(lru_post):]
            for i in range(0, NUMWAYS):
                value = True
                for j in range(0, NUMWAYS):
                    value = value and expand[i][j]
                temp[i] = value
            lru_post.next = temp

            # **********************************************************************
            # This final step is equal to step 2 and also clear now.
            #
            # lru_post[1] = &expand[1] = 1'b1;
            #
            # lru_post = 4'b0010 is what we expected.
            # **********************************************************************
    else:
        # Ignore lru_post
        @always_comb
        def step_1():
            expand   = [modbv(0)[NUMWAYS:] for i in range(NUMWAYS)]
            offset = 0

            # 1. Fill the matrix (expand) with the values. The entry (i,i) is
            #    statically one.
            for i in range(0, NUMWAYS):
                expand[i][i] = True

                for j in range(i + 1, NUMWAYS):
                    expand[i][j] = current[offset + j - i - 1]
                for j in range(0, i):
                    expand[i][j] = not expand[j][i]

                offset = offset + NUMWAYS - i - 1

            tmp0 = modbv(0)[NUMWAYS:]
            for i in range(0, NUMWAYS):
                value = True
                for j in range(0, NUMWAYS):
                    value = value and expand[i][j]
                tmp0[i] = value
            lru_pre.next = tmp0

            for i in range(0, NUMWAYS):
                if access[i]:
                    for j in range(0, NUMWAYS):
                        if i != j:
                            expand[i][j] = False
                    for j in range(0, NUMWAYS):
                        if i != j:
                            expand[j][i] = True

            offset = 0
            tmp1 = modbv(0)[len(update):]
            for i in range(0, NUMWAYS):
                for j in range(i + 1, NUMWAYS):
                    tmp1[offset + j - i - 1] = expand[i][j]
                offset = offset + NUMWAYS - i - 1
            update.next = tmp1

    return instances()

# Local Variables:
# flycheck-flake8-maximum-line-length: 120
# flycheck-flake8rc: ".flake8rc"
# End:

#!/usr/bin/env python

import sys
import random

# Copyright 2017 ETH Zurich and University of Bologna.
# Copyright and related rights are licensed under the Solderpad Hardware
# License, Version 0.51 (the License); you may not use this file except in
# compliance with the License.  You may obtain a copy of the License at
# http://solderpad.org/licenses/SHL-0.51. Unless required by applicable law
# or agreed to in writing, software, hardware and materials distributed under
# this License is distributed on an AS IS BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.


def write_arr(f, name, arr, ctype, size, linebreak):
    f.write(ctype + " " + name + "[] = {\n\t")
    i = 1
    for v in arr:
        if i % size == 0:
            f.write("%d};\n\n" % (v))
        elif i % linebreak == 0:
            f.write("%d,\n\t" % (v))
        else:
            f.write("%d," % (v))
        i += 1
    return


################################################################################
f = open("conv1Di32.h", "w")
f.write("#ifndef _CONV1Di32 \n")
f.write("#define _CONV1Di32 \n")
f.write("// This file is automatically generated\n")


N = 16
IC = 4
OC = 16
W = 4
RANGE = 4095

data = []
kernel = []
expected = []

pad = 1

# N C W format
for i in range(0, IC):
    for j in range(0, N):
        data.append(j)
        # data.append(random.randint(-RANGE, RANGE-1))

# O I W format
for i in range(0, OC):
    for j in range(0, IC):
        for k in range(0, W):
            kernel.append(i * 100 + j * 10 + k)
            # kernel.append(random.randint(-RANGE, RANGE-1))

# O W format
for i in range(0, OC):
    for j in range(0, N):
        sum = 0
        for w_i in range(0, W):
            for w_j in range(0, IC):
                data_idx = j + w_i
                data_at_idx = 0
                if data_idx < N:
                    data_at_idx = data[w_j * N + j + w_i]
                sum += kernel[(IC * i + w_j) * W + w_i] * data_at_idx
        expected.append(sum)


write_arr(
    f,
    "DATA",
    data,
    'int32_t __attribute__((section(".xheep_data_interleaved")))',
    IC * N,
    128,
)
write_arr(
    f,
    "KERNELS",
    kernel,
    'int32_t __attribute__((section(".xheep_data_interleaved")))',
    OC * IC * W,
    128,
)
write_arr(
    f,
    "EXPECTED",
    expected,
    'int32_t __attribute__((section(".xheep_data_interleaved")))',
    OC * N,
    128,
)

f.write("#define N %d\n" % N)
f.write("#define IC %d\n" % IC)
f.write("#define W %d\n" % W)
f.write("#define OC %d\n" % OC)
f.write("#define PAD %d\n" % 1)


f.write("#endif")

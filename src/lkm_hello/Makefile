# https://www.kernel.org/doc/html/latest/kbuild/modules.html

ifneq ($(KERNELRELEASE),)
# kbuild part of makefile
obj-m := lkm_hello.o

ccflags-y := -Wall
# -g 無くても -g -gdwarf-5 つく

else
# normal makefile
KDIR ?= /lib/modules/`uname -r`/build/
# MO= : >= 6.13 https://github.com/torvalds/linux/commit/11b3d5175e6bc3779159228e6077be202d2b0069
MO ?= $(CURDIR)/build/

default:
	$(MAKE) -C $(KDIR) M=$(CURDIR) MO=$(MO) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) MO=$(MO) clean
	rm -rf $(MO)

.PHONY: default clean

endif

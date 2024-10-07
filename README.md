# pueo-utils

All of these things require xsdb/xsct, which requires Vivado Lab because Xilinx thinks hey, what's a
gigabyte between friends.

You can, however, load a drastically reduced number of files and xsdb will work. I can't put that
here, but if you run ``package.sh`` _in the install directory_ it will neatly package it up for you
(e.g. run package.sh in ``Xilinx/Vivado_Lab/2022.2/``) into ``standalone_xsdb.tar.gz``. Then put 
the ``standalone_xsdb`` script here into the ``xsdb/`` directory, and Bob's your uncle.

Standalone xsdb takes about 5 megabytes and loads wacko fast.

You probably also need hw_server, though (although xsdb can access a server on another physical machine).
There is also a ``package_hwserver.sh`` script, which will make a standalone hw_server, and then
you can use ``standalone_hw_server``.

By default though this won't allow accessing any devices (other than an xvc device, probably?)
since no drivers are there. The easiest way to fix that is to use Digilent devices and install
Digilent Adept Runtime, which (shock!) is nicely packaged for Linux.

https://lp.digilent.com/complete-adept-runtime-download

### tl;dr

1. Install [Digilent Adept runtime|https://lp.digilent.com/complete-adept-runtime-download].
2. Run ``package.sh`` and ``package_hwserver.sh`` in an Vivado Lab install directory.
3. Move ``standalone_xsdb.tar.gz`` and ``standalone_hw_server.tar.gz`` to machine you want to install stuff on.
4. Unpack both of them.
5. Run standalone_hw_server first, then you can run standalone_xsdb.

It should be fairly obvious how this works, the scripts are like 3 lines long.
Figure it out.

## Host utilities

* jtransfer: horrible Python script to transfer files via the JTAG terminal using hex encoding (super slow)
* jdownload: in-progress Python script to handle bulk file downloads via dow/jdld/jtag terminal

## Target utilities

* jdld: Program running on PetaLinux acting as a JTAG download daemon.
* jc/jb: Program running on PetaLinux to allow easy console commanding. jb is just jc with no echoing.


# Details on standalone xsdb

* ``rdi_xsdb`` from e.g. ``Xilinx/Vivado_Lab/2022.2/bin/unwrapped/lnx64.o/rdi_xsdb``
* ``libtcl8.5.so`` from e.g. ``Xilinx/Vivado_Lab/2022.2/lib/lnx64.o/libtcl8.5.so``
* ``libtcltcf.so`` from e.g. ``Xilinx/Vivado_Lab/2022.2/lib/lnx64.o/libtcltcf.so``
* the tcl8.5 library from e.g. ``Xilinx/Vivado_Lab/2022.2/tps/tcl/tcl8.5`` installed under $HOME/lib
* the xsdb library from e.g. ``Xilinx/Vivado_Lab/2022.2/scripts/xsdb/xsdb`` installed under $HOME/lib
* the tcf library from e.g. ``Xilinx/Vivado_Lab/2022.2/scripts/xsdb/tcf`` installed under $HOME/lib
* the ``cmdline``, ``control``, ``fileutil``, ``json``, and ``uuid`` packages from
  e.g. ``Xilinx/Vivado_Lab/2022.2/tps/tcl/tcllib1.11.1/`` installe under $HOME/lib.

plus optionally the completion list from
* the completion list ``cmdlist`` from e.g. ``Xilinx/Vivado_Lab/2022.2/scripts/xsdb/xsdb/cmdlist``

Running ``rdi_xsdb`` obviously requires modifying ``LD_LIBRARY_PATH`` to be able to see the two
shared library files.

To get the same experience that Xilinx gives with ``xsdb``, you need to run it through rlwrap,
grabbing a history from somewhere and using the completion list.

### standalone xsdb speed

```
$ time standalone_xsdb -eval "puts \"hello world\""
hello world

real    0m0.064s
user    0m0.049s
sys     0m0.016s
```

### xilinx xsdb speed

```
$ time xsdb -eval "puts \"hello world\""
hello world

real    0m3.320s
user    0m3.218s
sys     0m0.123s
```
yeah, you got me.

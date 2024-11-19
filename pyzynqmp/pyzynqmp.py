import os
import struct
import shutil

# parses header for bitstream
class Bitstream:
    HEADER=b'\x00\t\x0f\xf0\x0f\xf0\x0f\xf0\x0f\xf0\x00\x00\x01'
    def __init__(self, fn):
        self.fn = fn
        with open(fn, "rb") as f:
            hc = f.read(len(self.HEADER))
            if hc != self.HEADER:
                raise TypeError("bit header not present")
            keydlen = f.read(3)
            dl, = struct.unpack(">H", keydlen[1:3])
            designStr = f.read(dl)[:-1].decode()
            designFields = designStr.split(";")
            self.design = designFields[0]
            self.userid = int(designFields[1].split("=")[1],16)
            self.toolVersion = designFields[2].split("=")[1]
            keylen = f.read(3)
            dvl, = struct.unpack(">H", keylen[1:3])
            self.device = f.read(dvl)[:-1].decode()
            keydtlen = f.read(3)
            dtl, = struct.unpack(">H", keydtlen[1:3])
            self.date = f.read(dtl)[:-1].decode()
            keytmlen = f.read(3)
            tml, = struct.unpack(">H", keytmlen[1:3])
            self.time = f.read(tml)[:-1].decode()
            keyllen = f.read(5)
            llen, = struct.unpack(">I", keyllen[1:5])
            self.length = llen

# this is an abstraction of the SoC for Python code
# *running on the SoC*
# it can:
# - program it via the sysfs interface
# - perform readback capture via sysfs interface
# - read out sensors via IIO stuff
# - read DNA/IDCODE/etc. via pm and efuse
# - read pggs registers
# It doesn't hold any resources open when it does this stuff
# so it's perfectly fine to be instantiated in multiple places.
#
# this replaces a ton of fpgautil, but that's okay because
# fpgautil is braindead
class PyZynqMP:
    NVMEM_PATH="/sys/bus/nvmem/devices/zynqmp-nvmem0/nvmem"
    FPGAMGR_PATH="/sys/class/fpga_manager/fpga0/"
    LIBFIRMWARE_PATH="/lib/firmware/"
    MODPARAM_PATH="/sys/module/zynqmp_fpga/parameters/"
    DEBUG_PATH="/sys/kernel/debug/"
    STATE_PATH=FPGAMGR_PATH+"state"
    FLAGS_PATH=FPGAMGR_PATH+"flags"
    FIRMWARE_PATH=FPGAMGR_PATH+"firmware"
    STATE_OPERATING='operating'
    # defines
    idcode_map = { 0x147E5093 : "xczu25dr",
                   0x147FF093 : "xczu47dr" }
    
    # IIO
    IIO_PATH="/sys/bus/iio/devices/"
    IIO_DEVICE="iio:device0/"
    IIO_DEVICE_PATH=IIO_PATH+IIO_DEVICE

    # GGS/PGGS
    GGS_PATH="/sys/devices/platform/firmware:zynqmp-firmware/"
    
    # PM (chipid)
    PM_PATH=DEBUG_PATH+"zynqmp-firmware/pm"
    PM_CHIPID="pm_get_chipid\n"

    # these are in progress
    READBACK_TYPE_PATH=MODPARAM_PATH+"readback_type"
    READBACK_LEN_PATH=MODPARAM_PATH+"readback_len"
    IMAGE_PATH=DEBUG_PATH+"fpga/fpga0/image"


    SILICON_VERSION_OFFSET = 0
    PS_DNA_OFFSET = 12

    # fixed to volts, not millivolts
    IIO_VOLT_SCALE=0.000045776367
    IIO_TEMP_SCALE=0.007771514892
    IIO_TEMP_OFFSET=-36058

    # this is kinda PUEO-specific
    # we only grab an example of each voltage. read from power structure TE0835
    # ----0.853 is PL (VCCINT_0V85)
    # ----3.3 is PL (VCC_B88_HD)
    # 0.85 PSINTLP/FP/FP_DDR
    # 1.8 PSAUX/ADC/IO/DDR_PLL/VCCAUX/VCCAUX_IO
    # 1.8 MGTRAVTT
    # 0.85 MGTRAVCC/MGTAVTT 
    # 1.2 MGTAVTT/PSPLL
    # ----0.9 MGTAVCC is PL only
    # 1.2 PSDDR
    # ----0.8534V VCCINT_AMS is PL only
    # ----0.925V ADC_AVCC is PL only
    # ----1.8V ADC_AVCCAUX is PL only
    # ----0.925V DAC_AVCC is PL only
    # ----1.8V DAC_AVCCAUX is PL only
    # ----2.5V DAC_AVTT is PL only
    iio_temps = { "RPUTEMP" : "in_temp0_ps_temp_raw",
                  "APUTEMP" : "in_temp1_remote_temp_raw" }
    iio_volts = { "PSINTLP" : "in_voltage7_vccpsintlp_raw",
                  "PSAUX" : "in_voltage9_vccpsaux_raw",
                  "MGTRAVTT" : "in_voltage16_psmgtravtt_raw",
                  "MGTRAVCC" : "in_voltage15_psmgtravcc_raw",
                  "PSPLL" : "in_voltage0_vcc_pspll0_raw",
                  "PSDDR" : "in_voltage10_vccpsddr_raw" }
    
    def __init__(self):
        # grab the idcode and version (whaaatever)
        open(self.PM_PATH, "w").write(self.PM_CHIPID)
        chipidtok = open(self.PM_PATH).read().split(':')
        # pm_get_chipid returns 'Idcode: 0xIDCODE, Version:0xVERSION'
        self.idcode = int(chipidtok[1].split(',')[0], base=16)
        self.device = self.idcode_map.get(self.idcode, 'Unknown')
        self.version = int(chipidtok[2], base=16)
        # we can grab and store the eFuse crap internally
        # since it's static
        fd = os.open(self.NVMEM_PATH, os.O_RDONLY)
        # silicon version
        rb = os.pread(fd, 4, self.SILICON_VERSION_OFFSET)
        self.silicon_version = struct.unpack('I', rb)[0]
        # dna
        rb = os.pread(fd, 12, self.PS_DNA_OFFSET)
        dnaVals = struct.unpack('III', rb)
        # we store as a string
        self.dna = ('%8.8x' % dnaVals[2])
        self.dna += ('%8.8x' % dnaVals[1])
        self.dna += ('%8.8x' % dnaVals[0])

    def state(self):
        return open(self.STATE_PATH).read()[:-1]
    
    def running(self):
        state = self.state()
        return state == self.STATE_OPERATING

    def load(self, filename):
        if not os.path.isfile(filename):
            raise FileNotFoundError("%s does not exist" % filename)
        # check if it's an actual bitstream
        b = Bitstream(filename)
        # check if it's for *us*
        dev = b.device.split('-')[0]
        if dev != self.device:
            raise TypeError("%s is for a %s, this is a %s" %
                            (filename, dev, self.device))
        basefn = os.path.basename(filename)
        libfirmwarefn = self.LIBFIRMWARE_PATH + basefn
        # our flags are always 0 because it's a full load
        fd = os.open(self.FLAGS_PATH, os.O_WRONLY)
        os.write(fd, b'0\n')
        os.close(fd)
        # check to see if we even need to do anything
        if libfirmwarefn != filename:
            shutil.copyfile(filename, libfirmwarefn)
        # ok, now that it's there, load it
        fd = os.open(self.FIRMWARE_PATH, os.O_WRONLY)
        os.write(fd, bytes(basefn+'\n', encoding='utf-8'))
        os.close(fd)
        # update the current pointer
        libcurfn = self.LIBFIRMWARE_PATH + "current"
        if os.path.exists(libcurfn):
            os.remove(libcurfn)        
        os.symlink(libfirmwarefn, libcurfn)
        return True

    def raw_iio(self, fnList):
        if type(fnList) is not list:
            fnList = [ fnList ]
        rv = []
        for fn in fnList:
            rv.append(int(open(self.IIO_DEVICE_PATH+fn).read()))
        return rv
    
    def raw_volts(self):
        return self.raw_iio(list(self.iio_volts.values()))

    def raw_temps(self):
        return self.raw_iio(list(self.iio_temps.values()))

    def monitor(self):
        for tempKey in self.iio_temps:
            val = self.raw_iio(self.iio_temps[tempKey])[0]
            print("%s : %f C" % (tempKey, (val+self.IIO_TEMP_OFFSET)*self.IIO_TEMP_SCALE))
        for voltKey in self.iio_volts:
            val = self.raw_iio(self.iio_volts[voltKey])[0]
            print("%s : %f V" % (voltKey, val*self.IIO_VOLT_SCALE))

    def pggs(self, num):
        return int(open(self.GGS_PATH+"pggs%d" % num).read(),16)

    def ggs(self, num):
        return int(open(self.GGS_PATH+"ggs%d" % num).read(),16)
        
            
if __name__ == "__main__":
    import sys
    
    zynq = PyZynqMP()
    # third option needed only for load/ggs/pggs
    fi = None if len(sys.argv)<3 else sys.argv[2]
    # map arguments to functions
    fnMap = { 'monitor' : zynq.monitor,
              'dna' : lambda z=zynq : print(z.dna),
              'device' : lambda z=zynq : print(z.device),
              'state' : lambda z=zynq : print(z.state()),
              'ggs' : lambda z=zynq,arg=fi : z.ggs(int(arg)) if arg is not None else print("Need a GGS number"),
              'pggs' : lambda z=zynq,arg=fi : z.pggs(int(arg)) if arg is not None else print("Need a PGGS number"),
              'load' : lambda z=zynq,arg=fi : z.load(arg) if arg is not None else print("Need a filename") }
    
    if len(sys.argv) < 2:
        fn = None
    else: 
        fn = fnMap.get(sys.argv[1], None)
        
    if fn is None:
        keys = ' '.join(list(fnMap.keys()))
        print("Specify one: %s" % keys)
    else:
        fn()

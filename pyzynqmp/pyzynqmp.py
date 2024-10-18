import os
import struct
import shutil

# this is an abstraction of the SoC for Python code
# *running on the SoC*
# it can:
# - program it via the sysfs interface
# - perform readback capture via sysfs interface
# - read out sensors via IIO stuff
# - read DNA via nvmem EFUSE stuff
# It doesn't hold any resources open when it does this stuff
# so it's perfectly fine to be instantiated in multiple places.
#
# this replaces a ton of fpgautil, but that's okay because
# fpgautil is braindead
class PyZynqMP:
    NVMEM_PATH="/sys/bus/nvmem/devices/zynqmp-nvmem0/nvmem"
    FPGAMGR_PATH="/sys/class/fpga_manager/fpga0/"
    MODPARAM_PATH="/sys/module/zynqmp_fpga/parameters/"
    DEBUG_PATH="/sys/kernel/debug/"
    STATE_PATH=FPGAMGR_PATH+"state"
    FLAGS_PATH=FPGAMGR_PATH+"flags"
    FIRMWARE_PATH=FPGAMGR_PATH+"firmware"
    STATE_OPERATING=b'operating\n'
    IIO_PATH="/sys/bus/iio/devices/"
    IIO_DEVICE="iio:device0/"
    IIO_DEVICE_PATH=IIO_PATH+IIO_DEVICE
    # these are in progress
    READBACK_TYPE_PATH=MODPARAM_PATH+"readback_type"
    READBACK_LEN_PATH=MODPARAM_PATH+"readback_len"
    IMAGE_PATH=DEBUG_PATH+"fpga/fpga0/image"
    PM_PATH=DEBUG_PATH+"zynqmp-firmware/pm"
    SILICON_VERSION_OFFSET = 0
    PS_DNA_OFFSET = 12

    # fixed to volts, not millivolts
    IIO_VOLTAGE_SCALE=0.000045776367
    IIO_TEMP_SCALE=0.007771514892
    IIO_TEMP_OFFSET=-36058
    
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
        # we can grab and store the eFuse crap internally
        # since it's static
        fd = os.open(NVMEM_PATH, os.O_RDONLY)
        # silicon version
        rb = os.pread(fd, 4, SILICON_VERSION_OFFSET)
        self.silicon_version = struct.unpack('I', rb)[0]
        # dna
        rb = os.pread(fd, 12, PS_DNA_OFFSET)
        dnaVals = struct.unpack('III', rb)
        # we store as a string
        self.dna = ('%8.8x' % dnaVals[2])
        self.dna += ('%8.8x' % dnaVals[1])
        self.dna += ('%8.8x' % dnaVals[0])

    def state(self):
        # do... do you know what fpgautil does here
        # it cats the output to a file and reads it
        # what... the...
        fd = os.open(STATE_PATH, os.O_RDONLY)
        # this can only be a small length, like under 32 or some'n
        state = os.read(fd, 32)
        os.close(fd)
        return state
    
    def running(self):
        state = self.state()
        return state == STATE_OPERATING

    def load(self, filename):
        if not os.path.isfile(filename):
            print("%s does not exist?" % filename)
            return False
        # our flags are always 0 because it's a full load
        fd = os.open(FLAGS_PATH, os.O_WRONLY)
        os.write(fd, b'0\n')
        os.close(fd)
        # we can just use shutil because it'll use sendfile, wee!
        shutil.copyfile(filename, FIRMWARE_PATH)
        return True

    def raw_iio(self, fnList):
        if type(fnList) is not list:
            fnList = [ fnList ]
        rv = []
        for fn in fnList:
            rv.append(int(open(IIO_DEVICE_PATH+fn).read()))
        return rv
    
    def raw_volts(self):
        return self.raw_iio(list(iio_volts.values()))

    def raw_temps(self):
        return self.raw_iio(list(iio_temps.values()))

    def monitor(self):
        for tempKey in iio_temps:
            val = raw_iio(iio_temps[tempKey])
            print("%s : %f C" % (tempKey, (val+IIO_TEMP_OFFSET)*IIO_TEMP_SCALE))
        for voltKey in iio_volts:
            val = raw_iio(iio_volts[voltKey])
            print("%s : %f V" % (voltKey, val*IIO_VOLT_SCALE))
    
    def version(self):
        return self.silicon_version
    
    def dna(self):
        return self.dna
        


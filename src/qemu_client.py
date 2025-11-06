import os
import subprocess

class DataCollector:
    cmd = None
    err_file = None
    out_file = None

    def run(self):
        if self.cmd != None:
            os.system("%s 2>%s >%s" % (self.cmd, self.err_file, self.out_file))

class RedisDataCollector(DataCollector):
    def __init__(self, prefix):
        err_file = "redis_bench.err"
        out_file = "redis_bench.out"
        self.out_file = prefix + out_file
        self.err_file = prefix + err_file
        self.cmd = "redis-benchmark --csv"

# redis benchmark数据文件存放位置，绝对路径，尾部需要写/
# 在该路径指向的目录下，将会新建redis_benchmark.out和redis_benchmark.err
REDIS_BENCH_OUTPUT = '/mnt/'

print('REDIS_BENCH_OUTPUT is %s\n' % REDIS_BENCH_OUTPUT)
redis_collector = RedisDataCollector(REDIS_BENCH_OUTPUT)
redis_collector.run()
subprocess.run('shutdown', shell=True)

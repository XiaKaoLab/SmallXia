"""运行独立积木 Python 程序；停止时中断等待并清理本程序创建的任务。
Created on 2026-11-02; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import os
from pathlib import Path
import sys
from threading import Thread
from time import time_ns

from ..imitation.api_worker import ImitationWorker


class ProgramWorker(ImitationWorker):
    def run(self):
        from ..blocks.workflow import BlockWorkflow
        os.environ['XIAOXIA_PROGRAM_DIR'] = str(self.directory)
        Thread(target=self.watch_parent, daemon=True).start()
        def checkpoint(frame, event, arg):
            filename = frame.f_code.co_filename
            interruptible = filename == '<blocks>' or ('xiaoxia_core' in filename and ('blocks' in filename or filename.endswith('hardware_client.py'))
                and frame.f_code.co_name not in ('http', 'track', 'track_created', 'cleanup'))
            if interruptible and (self.directory / 'stop').exists():
                raise InterruptedError('程序已停止')
            return checkpoint
        self.progress(status='running', started_at_ns=time_ns())
        try:
            sys.settrace(checkpoint)
            exec(compile(self.request['source'], '<blocks>', 'exec'), {'__name__': '__main__'})
            sys.settrace(None)
            BlockWorkflow().cleanup(self.directory, hardware_only=True)
            self.progress(status='succeeded', finished_at_ns=time_ns())
        except BaseException as error:
            sys.settrace(None)
            BlockWorkflow().cleanup(self.directory)
            self.progress(status='cancelled' if isinstance(error, InterruptedError) else 'failed',
                          error=str(error), finished_at_ns=time_ns())
        finally:
            sys.settrace(None)


if __name__ == '__main__':
    ProgramWorker(Path(sys.argv[1])).run()

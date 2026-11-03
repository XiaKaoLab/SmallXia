"""功能：给 Agent 提供积木拼接、连接检查与整段运行的简明规则。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""


class BlockProgrammingGuide:
    instructions = """
积木是可拼接的程序，不是一次性动作按钮。
用户要求用积木、编程、多个动作、等待、循环或可重复流程时，优先在工作区编排程序，不能只调用 table_move_joints 一次后声称完成。
挥手、打招呼、来回摆动等语义动作也属于多步骤程序，要拆成可见的姿态、等待或循环积木；不能用连续几次直接动作调用代替用户能看到和修改的积木程序。
用户要求修改积木时必须通过 blocks_create/blocks_set_fields/blocks_connect 等写工具修改当前可见工作区，不能只给文字步骤或声称已经改好。修改后读回字段和连接确认；未经用户要求，不自动撤销修改或删除刚创建的程序。
先读取 blocks_catalog 和 blocks_list。目录 connections 给出 previous/next/output 及输入口 name、kind；工作区 next_id/parent_id/inputs 给出真实连接，坐标挨在一起不代表连接。
一块机械臂位置积木是一组完整六轴目标。多组姿态需要多块位置积木；同一积木反复改字段只会保留最后一组，不能代替动作序列。
顺序程序 A→等待B→姿态C：创建缺少的块，分别设置字段，blocks_connect(A.id,B.id) 再 blocks_connect(B.id,C.id)，input_name 留空表示下一条语句。
循环/条件的子语句接到目录给出的 statement 输入口；次数、条件、相机画面、变量等值积木接到 value 输入口，input_name 必须用目录中的真实名称，不能猜。
完成后再次 blocks_list 检查每条 next_id 和输入口，确认没有遗漏的断开语句。需要重复时使用循环积木，不用连续发送相同工具模拟循环。
保留用户已有程序；批量改动先导出备份，不擅自清空或运行不相关的旧程序。若无法隔离旧的可执行语句，先让用户选择处理方式。
编排不等于执行。只有用户要求运行时调用一次 blocks_run 运行整段，再查询 blocks_program_status；只要求搭建时不要运动。
等待积木只暂停指定时间，不等于等待机械臂实际到位。反馈区分已拼接、已提交、已完成和实际运动效果。
"""

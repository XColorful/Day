import os
import time
import msvcrt  # Windows 下的文件锁
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import shutil

# 设置工作目录到代码所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 文件相关操作
def read_settings(file_path):
    settings = {"tasksdir": ".\\tasks.txt",
                "daydir": ".\\day",
                "lockdir": ".\\lock.txt",
                "historydir": ".\\history",
                "historycopy": 0,
                "historydelete": 3}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                key, value = line.strip().split(':', 1)
                if key in ["historycopy", "historydelete"]:
                    settings[key] = int(value.strip())
                else:
                    settings[key] = value.strip()
    return settings

def read_tasks(file_path):
    tasks = []
    total_minutes = 0
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                task_name, minutes = line.strip().split(',')
                tasks.append({'name': task_name, 'total_minutes': int(minutes), 'progress': 0, 'is_running': False})
                total_minutes += int(minutes)
    return tasks, total_minutes

def read_log(file_path):
    log = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    task_name, timestamp, action = line.strip().split(',')
                    timestamp = datetime.strptime(timestamp[:16], '%Y_%m_%d-%H:%M').strftime('%Y_%m_%d-%H:%M')
                    dt = datetime.strptime(timestamp, '%Y_%m_%d-%H:%M')  # 验证时间格式
                    if task_name not in log:
                        log[task_name] = []
                    if action == '开始':
                        if not log[task_name] or log[task_name][-1][1] != '开始':
                            log[task_name].append((timestamp, action))
                    elif action == '结束':
                        if log[task_name] and log[task_name][-1][1] == '开始':
                            log[task_name].append((timestamp, action))
                except (ValueError, IndexError):
                    continue
    return log

def append_log(file_path, task_name, action):
    timestamp = datetime.now().strftime('%Y_%m_%d-%H:%M')
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f"{task_name},{timestamp},{action}\n")

# 锁定文件机制：使用 msvcrt 实现文件锁
def check_and_set_lock(lock_file):
    try:
        if not os.path.exists(lock_file):
            with open(lock_file, 'w') as f:
                pass
        lock_fd = open(lock_file, 'a')  # 打开文件以便进行锁定
        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)  # 尝试获取锁，非阻塞模式
        return lock_fd
    except IOError as e:
        print(f"程序已经运行，无法获取锁：{e}")
        return None


def release_lock(lock_fd):
    if lock_fd:
        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)  # 释放锁
        lock_fd.close()

def manage_history(daydir, historydir, historycopy, historydelete):
    current_date = datetime.now()
    if not os.path.exists(daydir):
        os.makedirs(daydir)
    if not os.path.exists(historydir):
        os.makedirs(historydir)

    if not os.path.exists(daydir):
        os.makedirs(daydir)
    for file_name in os.listdir(daydir):
        try:
            file_date = datetime.strptime(file_name[:10], '%Y_%m_%d')
            file_path = os.path.join(daydir, file_name)

            # 复制到历史目录
            if historycopy >= 0 and (current_date - file_date).days > historycopy:
                target_path = os.path.join(historydir, file_name)
                if not os.path.exists(target_path):
                    shutil.copy(file_path, target_path)

            # 删除旧文件
            if historydelete >= 0 and (current_date - file_date).days > historydelete:
                os.remove(file_path)

        except ValueError:
            continue

# 时间计算
def calculate_progress(log, tasks):
    for task in tasks:
        if task['name'] in log:
            total_time = 0
            start_time = None
            for timestamp, action in log[task['name']]:
                dt = datetime.strptime(timestamp, '%Y_%m_%d-%H:%M')
                if action == '开始':
                    start_time = dt
                elif action == '结束' and start_time:
                    elapsed = (dt - start_time).total_seconds() / 60
                    total_time += max(elapsed, 0)
                    start_time = None
            if start_time:
                total_time += (datetime.now() - start_time).total_seconds() / 60
            task['progress'] = min(total_time, task['total_minutes'])
            task['is_running'] = start_time is not None

def calculate_total_progress(tasks, total_minutes):
    total_progress = sum(task['progress'] for task in tasks)
    return min(total_progress / total_minutes, 1.0) if total_minutes > 0 else 0

def adjust_task_bar_length(tasks, max_length=200):
    if (len(tasks) == 0): return
    max_minutes = max(task['total_minutes'] for task in tasks)
    for task in tasks:
        task['bar_length'] = max(50, int(max_length * (task['total_minutes'] / max_minutes)))

# 界面相关操作
def create_task_row(root, task, log_file, update_progress):
    frame = ttk.Frame(root)
    frame.pack(fill='x', padx=5, pady=2)

    label = ttk.Label(frame, text=task['name'], width=20, anchor='w')
    label.pack(side='left')

    progress_var = tk.StringVar()
    progress_bar = ttk.Progressbar(frame, length=task['bar_length'], maximum=task['total_minutes'], style=f"{task['name']}.Horizontal.TProgressbar")
    progress_bar.pack(side='left', padx=5)

    progress_label = ttk.Label(frame, textvariable=progress_var, width=20)
    progress_label.pack(side='left')

    button = ttk.Button(frame, text='开始' if not task['is_running'] else '结束', command=lambda: toggle_task(task, log_file, button, update_progress))
    button.pack(side='right', padx=5)

    def update():
        progress_bar['value'] = task['progress']
        progress_var.set(f"{int(task['progress'])}/{task['total_minutes']}分钟")

    return update

def toggle_task(task, log_file, button, update_progress):
    if task['is_running']:
        append_log(log_file, task['name'], '结束')
        task['is_running'] = False
        button.config(text='开始')
    else:
        append_log(log_file, task['name'], '开始')
        task['is_running'] = True
        button.config(text='结束')
    update_progress()

# 主程序
def main():
    settings = read_settings('settings.txt')
    tasks_file = os.path.join(settings['tasksdir'])
    log_file = os.path.join(settings['daydir'], datetime.now().strftime('%Y_%m_%d') + '.txt')
    lock_file = settings['lockdir']

    lock_fd = check_and_set_lock(lock_file)
    if not lock_fd:
        return  # 如果无法获取锁，退出程序

    try:
        tasks, total_minutes = read_tasks(tasks_file)
        log = read_log(log_file)

        calculate_progress(log, tasks)
        adjust_task_bar_length(tasks)

        manage_history(settings['daydir'], settings['historydir'], settings['historycopy'], settings['historydelete'])

        root = tk.Tk()
        root.title("Day")

        # 定义进度条样式
        style = ttk.Style(root)
        for task in tasks:
            style.configure(f"{task['name']}.Horizontal.TProgressbar", troughcolor='white', background='gold')

        total_progress_var = tk.StringVar()
        total_progress_label = ttk.Label(root, textvariable=total_progress_var)
        total_progress_label.pack()
        total_progress_bar = ttk.Progressbar(root, length=400, maximum=1.0)
        total_progress_bar.pack(pady=5)

        update_functions = []

        def update_progress():
            total_progress = calculate_total_progress(tasks, total_minutes)
            total_progress_var.set(f"总进度：{int(total_progress * 100)}%")
            total_progress_bar['value'] = total_progress
            for update_fn in update_functions:
                update_fn()

        for task in tasks:
            update_fn = create_task_row(root, task, log_file, update_progress)
            update_functions.append(update_fn)

        update_progress()

        def periodic_update():
            calculate_progress(read_log(log_file), tasks)
            update_progress()
            root.after(5000, periodic_update)  # 每5秒更新一次

        periodic_update()
        root.mainloop()
    
    finally:
        release_lock(lock_fd)  # 程序退出时释放锁

if __name__ == "__main__":
    main()

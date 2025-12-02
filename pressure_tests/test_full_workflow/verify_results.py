#!/usr/bin/env python3
"""
验证压力测试结果

检查：
1. 数据库中的测试会话记录
2. CSV 文件中的测试结果
3. 提供前端查看指引
"""

import sys
import os

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from sqlmodel import Session, select
from libs.ktem.ktem.db.models import engine, Conversation
import csv
from datetime import datetime, timedelta


def check_database():
    """检查数据库中的测试记录"""
    print("="*80)
    print("📊 数据库检查")
    print("="*80)
    
    # 查找最近创建的会话
    cutoff_time = datetime.now() - timedelta(hours=1)
    
    with Session(engine) as session:
        statement = select(Conversation).where(
            Conversation.date_created >= cutoff_time
        ).order_by(Conversation.date_created.desc())
        
        recent_convs = session.exec(statement).all()
        
        # 筛选有消息的会话
        valid_convs = [c for c in recent_convs if c.data_source.get('messages')]
        
        print(f"\n✓ 最近1小时内创建的会话: {len(recent_convs)} 个")
        print(f"✓ 其中有消息记录的: {len(valid_convs)} 个\n")
        
        if valid_convs:
            print("最新的3条测试会话：\n")
            for i, conv in enumerate(valid_convs[:3], 1):
                messages = conv.data_source.get('messages', [])
                print(f"{i}. 【{conv.name}】")
                print(f"   ID: {conv.id}")
                print(f"   对话轮数: {len(messages)}")
                print(f"   创建时间: {conv.date_created}")
                
                for j, msg in enumerate(messages, 1):
                    if isinstance(msg, list) and len(msg) >= 2:
                        q = msg[0][:35] if msg[0] else 'None'
                        a = msg[1][:50] if msg[1] else 'None'
                        print(f"     第{j}轮 - 问: {q}...")
                        print(f"            答: {a}...")
                print()
        else:
            print("⚠️  未找到有消息的测试会话\n")
        
        return len(valid_convs)


def check_csv():
    """检查 CSV 文件"""
    print("="*80)
    print("📄 CSV 文件检查")
    print("="*80)
    
    csv_file = os.path.join(os.path.dirname(__file__), "full_workflow_results.csv")
    
    if not os.path.exists(csv_file):
        print("\n✗ CSV 文件不存在\n")
        return 0
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 排除统计行
    data_lines = [l for l in lines if not l.startswith('AVERAGE') and not l.startswith('user_id')]
    
    print(f"\n✓ CSV 文件路径: {csv_file}")
    print(f"✓ 总记录数: {len(data_lines)}")
    
    # 统计成功/失败
    success_count = sum(1 for l in data_lines if ',success,' in l)
    failure_count = sum(1 for l in data_lines if ',failure,' in l)
    persisted_count = sum(1 for l in data_lines if 'persisted=yes' in l)
    
    print(f"✓ 成功: {success_count} | 失败: {failure_count}")
    print(f"✓ 已持久化: {persisted_count}\n")
    
    # 显示最后几条记录
    if data_lines:
        print("最新的3条测试记录：\n")
        for i, line in enumerate(data_lines[-3:], 1):
            parts = line.strip().split(',')
            if len(parts) >= 7:
                user_id = parts[0]
                question = parts[1][:40]
                duration = parts[5]
                status = parts[7]
                print(f"{i}. {user_id} | {question}... | {duration}s | {status}")
        print()
    
    return len(data_lines)


def show_frontend_guide():
    """显示前端查看指引"""
    print("="*80)
    print("🌐 前端查看指引")
    print("="*80)
    
    print("""
1. 打开浏览器访问: http://localhost:7860

2. 在左侧"聊天会话"面板中，你会看到所有测试会话，格式：
   - "Untitled - 2025-12-02 HH:MM:SS"  (测试产生的会话)
   - "压测_user_XXXX_时间戳"          (如果自定义了会话名)

3. 点击任意会话可查看完整对话历史

4. 测试产生的会话特征：
   - 创建时间在测试运行期间
   - 包含简单问答（"你好"、"介绍功能"等）
   - 或医疗病例对话（"患者男性65岁"等）

5. 如果看不到记录，尝试：
   - 刷新浏览器页面 (F5)
   - 点击左侧"新建聊天"按钮刷新列表
   - 检查是否使用了相同的用户登录（admin/admin）
""")


def main():
    print("\n" + "="*80)
    print(" 压力测试结果验证工具")
    print("="*80 + "\n")
    
    try:
        # 检查数据库
        db_count = check_database()
        
        # 检查 CSV
        csv_count = check_csv()
        
        # 显示前端指引
        show_frontend_guide()
        
        # 总结
        print("="*80)
        print("📋 验证总结")
        print("="*80)
        print(f"\n✓ 数据库有效会话: {db_count}")
        print(f"✓ CSV 测试记录: {csv_count}")
        
        if db_count > 0 and csv_count > 0:
            print("\n🎉 测试数据已成功保存，前端应该能看到历史记录！\n")
        elif db_count == 0:
            print("\n⚠️  数据库中没有测试记录，可能原因：")
            print("   1. 测试未运行或失败")
            print("   2. persist_data_source 未正确执行")
            print("   3. 检查 locust 日志中是否有错误\n")
        else:
            print("\n✓ 数据已保存，如前端看不到，请刷新页面\n")
            
    except Exception as e:
        print(f"\n✗ 验证过程出错: {str(e)}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

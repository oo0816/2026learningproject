"""
my-first-skill 配套脚本
=======================

这是 SKILL.md 引用的脚本示例。你需要根据自己选的 skill 主题来改。

当前是一个占位脚本——打印"我会被 skill 调用"。

实际使用时，skill 中的步骤可以写：
  "运行 python skills/my-first-skill/run_review.py <参数> 来执行 XX 操作"
"""

import sys


def main():
    print("=" * 50)
    print("my-first-skill 配套脚本")
    print("=" * 50)
    print()
    print("这个脚本会被你的 SKILL.md 引用。")
    print("根据你的 skill 主题来改写这个文件。")
    print()
    print(f"收到参数：{sys.argv[1:]}")


if __name__ == "__main__":
    main()

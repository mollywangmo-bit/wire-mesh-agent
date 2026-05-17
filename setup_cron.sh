#!/bin/bash
# 丝网行业研究 Agent - Cron 定时任务设置
# 每周一早上 8:00 执行

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_PATH=$(which python3)
# 添加 PATH 确保 cron 环境下能找到所有依赖
CRON_JOB="0 8 * * 1 cd $SCRIPT_DIR && PATH=/usr/local/bin:/usr/bin:/bin:/Library/Frameworks/Python.framework/Versions/3.11/bin && $PYTHON_PATH main.py >> /tmp/wire_mesh_cron.log 2>&1"

# 检查是否已有该任务
(crontab -l 2>/dev/null | grep -q "wire-mesh-agent") && {
    echo "已存在 wire-mesh-agent 的 cron 任务:"
    crontab -l | grep "wire-mesh-agent"
    echo ""
    echo "如需更新，请先运行: crontab -e"
    exit 0
}

# 添加任务
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ 已添加每周一 08:00 执行的 cron 任务"
echo ""
echo "当前 crontab:"
crontab -l
echo ""
echo "日志文件: /tmp/wire_mesh_cron.log"
echo "如需手动运行测试:"
echo "  cd $SCRIPT_DIR && python3 main.py"

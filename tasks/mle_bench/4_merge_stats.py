import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# 读取CSV文件
claude_stats = pd.read_csv('result/claude35/stats_df.csv')
openai_stats = pd.read_csv('result/openai/stats_df.csv')

# 获取最大提交数量作为基准
max_submissions = max(claude_stats.loc[claude_stats['Statistic'] == 'Total Submissions', 'Count'].values[0],
                      openai_stats.loc[openai_stats['Statistic'] == 'Total Submissions', 'Count'].values[0])

print(f"最大提交数量: {max_submissions}")

# 需要转换为比例的指标列表
metrics_to_convert = [
    'Gold Medals', 'Silver Medals', 'Bronze Medals', 
    'Total Medals', 'Valid Submissions', 'Above Median'
]

# 创建一个字典，用于存储转置后的数据
transposed_data = {
    'Model': ['Claude-3.5', 'GPT-4']
}

# 处理每个指标
for metric in metrics_to_convert:
    claude_value = claude_stats.loc[claude_stats['Statistic'] == metric, 'Count'].values[0]
    openai_value = openai_stats.loc[openai_stats['Statistic'] == metric, 'Count'].values[0]
    
    # 计算比例 (相对于最大提交数量)
    claude_ratio = claude_value / max_submissions
    openai_ratio = openai_value / max_submissions
    
    # 添加到转置后的数据，保存为浮点数
    transposed_data[metric] = [claude_ratio, openai_ratio]

# 转换为DataFrame
ratio_df = pd.DataFrame(transposed_data)

# 保存为CSV，以百分比格式显示
ratio_df_display = ratio_df.copy()
for metric in metrics_to_convert:
    ratio_df_display[metric] = ratio_df_display[metric].apply(lambda x: f"{x:.2%}")
ratio_df_display.to_csv('result/merged_stats_ratio.csv', index=False)

# 创建LaTeX表格 (适合论文)
latex_table = ratio_df.copy()
# 直接格式化浮点数为百分比
latex_output = latex_table.to_latex(index=False, 
                                   float_format=lambda x: f"{x:.2%}" if isinstance(x, (int, float)) else x,
                                   caption='比较Claude-3.5和GPT-4的性能指标比例（相对于最大提交数量）', 
                                   label='tab:model_ratio_comparison')
with open('result/merged_stats_ratio_latex.txt', 'w') as f:
    f.write(latex_output)

# 绘制可视化比较图
plt.figure(figsize=(10, 6))

# 设置图表样式
sns.set_style('whitegrid')
bar_width = 0.35
index = np.arange(len(metrics_to_convert))

# 获取每个模型的数据
claude_values = [ratio_df.loc[0, metric] for metric in metrics_to_convert]
openai_values = [ratio_df.loc[1, metric] for metric in metrics_to_convert]

# 绘制条形图
plt.bar(index - bar_width/2, claude_values, bar_width, label='Claude-3.5', color='#4e79a7')
plt.bar(index + bar_width/2, openai_values, bar_width, label='GPT-4', color='#f28e2c')

# 添加数值标签（百分比形式）
for i, v in enumerate(claude_values):
    plt.text(i - bar_width/2, v + 0.02, f"{v:.2%}", ha='center', fontsize=9)
    
for i, v in enumerate(openai_values):
    plt.text(i + bar_width/2, v + 0.02, f"{v:.2%}", ha='center', fontsize=9)

# 添加标签和标题
plt.xlabel('评估指标')
plt.ylabel('比例 (相对于最大提交数量)')
plt.title('Claude-3.5 vs GPT-4 性能比例比较')
plt.xticks(index, metrics_to_convert, rotation=45, ha='right')
plt.legend()
plt.ylim(0, max(max(claude_values), max(openai_values)) * 1.2)  # 为标签留出空间
plt.tight_layout()

# 保存图表
plt.savefig('result/model_ratio_comparison.png', dpi=300)
plt.savefig('result/model_ratio_comparison.pdf')

# 创建一个更学术的图表版本 (更适合论文)
plt.figure(figsize=(8, 5))
sns.set_style('whitegrid')
sns.set_context("paper", font_scale=1.2)

# 设置颜色
colors = ['#4e79a7', '#f28e2c']

# 准备数据以便使用seaborn的barplot
# 将数据重新转换为长格式
ratio_long = pd.melt(
    ratio_df, 
    id_vars=['Model'],
    value_vars=metrics_to_convert,
    var_name='Metric',
    value_name='Ratio'
)

# 创建分组条形图
g = sns.barplot(x='Metric', y='Ratio', hue='Model', data=ratio_long, palette=colors)

# 添加百分比标签
for i, bar in enumerate(g.patches):
    height = bar.get_height()
    g.text(bar.get_x() + bar.get_width()/2, height + 0.01, f"{height:.2%}", ha='center', fontsize=8)

# 优化图表
plt.xlabel('')
plt.ylabel('比例')
plt.title('Claude-3.5 与 GPT-4 性能指标比较')
plt.xticks(rotation=30, ha='right')
plt.legend(title='')
plt.tight_layout()
plt.ylim(0, max(ratio_long['Ratio']) * 1.15)  # 为标签留出空间

# 保存学术风格图表
plt.savefig('result/model_ratio_comparison_academic.png', dpi=400)
plt.savefig('result/model_ratio_comparison_academic.pdf')

print('比例统计合并完成! 输出文件:')
print('1. merged_stats_ratio.csv - 合并的比例CSV文件')
print('2. merged_stats_ratio_latex.txt - LaTeX表格格式')
print('3. model_ratio_comparison.png - 比例图表(PNG格式)')
print('4. model_ratio_comparison.pdf - 比例图表(PDF格式)')
print('5. model_ratio_comparison_academic.png - 论文风格图表(PNG格式)')
print('6. model_ratio_comparison_academic.pdf - 论文风格图表(PDF格式)') 
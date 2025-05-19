
def filter_duplicate_commands(commands):
    """
    简单的命令去重函数:
    1. 对带文件名的脚本，提取文件名进行匹配
    2. 对普通命令，去除空格后比较
    """
    import re
    
    unique_commands = []
    seen_filenames = set()  # 记录已见过的文件名
    seen_shell_cmds = set() # 记录已见过的shell命令
    
    for cmd_type, cmd_content in commands:
        # 检查是否包含文件名定义 (# filename: xxx)
        filename_match = re.search(r'#\s*filename:\s*([\w.-]+)', cmd_content)
        # import pdb; pdb.set_trace()
        # 
        if filename_match:
            # 有文件名，按文件名去重
            filename = filename_match.group(1)
            if filename not in seen_filenames:
                seen_filenames.add(filename)
                seen_shell_cmds.add(f"{cmd_type} {filename}")
                unique_commands.append([cmd_type, cmd_content])
        else:
            # 无文件名的shell命令，规范化后比较
            # 规范化: 去除前导/尾随空格，将多个空格替换为单个空格
            norm_content = re.sub(r'\s+', ' ', cmd_content.strip())            
            if norm_content not in seen_shell_cmds:
                seen_shell_cmds.add(norm_content)
                unique_commands.append([cmd_type, cmd_content])
    
    return unique_commands, seen_shell_cmds


def get_case_data():
  code_exec = [
    [
      "sh", "# filename: setup_environment.sh\npip install --quiet -v --no-cache-dir --global-option=\"--cpp_ext\" --global-option=\"--cuda_ext\" git+https://github.com/NVIDIA/apex\npip install git+https://github.com/mapillary/inplace_abn.git@v1.0.3"
    ],
    [
      "python", "# filename: train_and_infer.py\n\nimport os\nimport pandas as pd\nimport torch\nimport torch.nn as nn\nimport torch.optim as optim\nfrom torch.utils.data import DataLoader\nfrom torchvision import transforms\nfrom sklearn.metrics import cohen_kappa_score\nfrom retinopathy.dataset import RetinopathyDataset\nfrom retinopathy.models.common import get_model\nfrom retinopathy.train_utils import train_model, save_checkpoint, load_checkpoint\n\n# \u8bbe\u7f6e\u8bbe\u5907\ndevice = torch.device('cuda' if torch.cuda.is_available() else 'cpu')\n\n# \u6570\u636e\u8def\u5f84\ndata_dir = '/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/coding/0dfe0bc4-ca8d-412a-a271-5cf7e0576f38/data_small'\n\n# \u52a0\u8f7d\u6570\u636e\ntrain_df = pd.read_csv(os.path.join(data_dir, 'train.csv'))\ntest_df = pd.read_csv(os.path.join(data_dir, 'test.csv'))\n\n# \u6570\u636e\u9884\u5904\u7406\ntransform = transforms.Compose([\n    transforms.Resize((224, 224)),\n    transforms.ToTensor(),\n])\n\ntrain_dataset = RetinopathyDataset(train_df, data_dir, transform=transform)\ntest_dataset = RetinopathyDataset(test_df, data_dir, transform=transform, train=False)\n\ntrain_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, num_workers=4)\ntest_loader = DataLoader(test_dataset, batch_size=32, shuffle=False, num_workers=4)\n\n# \u5b9a\u4e49\u6a21\u578b\nmodel = get_model('resnet18', num_classes=5, pretrained=True)\nmodel = model.to(device)\n\n# \u5b9a\u4e49\u635f\u5931\u51fd\u6570\u548c\u4f18\u5316\u5668\ncriterion = nn.CrossEntropyLoss()\noptimizer = optim.Adam(model.parameters(), lr=1e-4)\n\n# \u8bad\u7ec3\u6a21\u578b\nnum_epochs = 2\nfor epoch in range(num_epochs):\n    train_model(model, train_loader, criterion, optimizer, epoch, device)\n    save_checkpoint(model, optimizer, epoch, 'checkpoints')\n\n# \u52a0\u8f7d\u6a21\u578b\u8fdb\u884c\u63a8\u7406\nload_checkpoint(model, optimizer, 'checkpoints', device)\nmodel.eval()\n\npredictions = []\nwith torch.no_grad():\n    for images, _ in test_loader:\n        images = images.to(device)\n        outputs = model(images)\n        _, preds = torch.max(outputs, 1)\n        predictions.extend(preds.cpu().numpy())\n\n# \u4fdd\u5b58\u7ed3\u679c\nsubmission_df = pd.DataFrame({'id_code': test_df['id_code'], 'diagnosis': predictions})\nsubmission_df.to_csv('test.csv', index=False)"
    ],
    [
      "sh", "   sh setup_environment.sh"
    ],
    [
      "sh", "   python train_and_infer.py"
    ]
  ]
  return code_exec

if __name__ == "__main__":

  code_exec = get_case_data()
  # 使用该函数过滤命令
  filtered_commands, seen_shell_cmds = filter_duplicate_commands(code_exec)
  print(filtered_commands)
  print(seen_shell_cmds)

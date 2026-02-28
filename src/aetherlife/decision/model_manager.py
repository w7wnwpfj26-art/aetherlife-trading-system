"""
模型管理器

负责RL模型的：
- 保存/加载
- 版本管理
- 性能追踪
- A/B测试
- 自动回滚
"""

import os
import json
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import numpy as np

from .ppo_agent import PPOTrainer, SACTrainer
from .rl_env import TradingEnv


class ModelMetadata:
    """模型元数据"""
    
    def __init__(
        self,
        model_id: str,
        algorithm: str,  # "PPO" or "SAC"
        version: str,
        created_at: datetime,
        trained_timesteps: int,
        performance_metrics: Dict[str, float],
        hyperparameters: Dict[str, Any],
        description: str = ""
    ):
        self.model_id = model_id
        self.algorithm = algorithm
        self.version = version
        self.created_at = created_at
        self.trained_timesteps = trained_timesteps
        self.performance_metrics = performance_metrics
        self.hyperparameters = hyperparameters
        self.description = description
    
    def to_dict(self) -> Dict:
        """转为字典"""
        return {
            "model_id": self.model_id,
            "algorithm": self.algorithm,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "trained_timesteps": self.trained_timesteps,
            "performance_metrics": self.performance_metrics,
            "hyperparameters": self.hyperparameters,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ModelMetadata":
        """从字典创建"""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class ModelManager:
    """
    模型管理器
    
    目录结构:
    models/
    ├── ppo_v1.0_20250221/
    │   ├── model.zip
    │   ├── metadata.json
    │   └── performance.json
    ├── sac_v1.0_20250221/
    │   ├── model.zip
    │   ├── metadata.json
    │   └── performance.json
    └── production/
        ├── current_model -> ../ppo_v1.0_20250221
        └── previous_model -> ../ppo_v0.9_20250220
    """
    
    def __init__(self, models_dir: str = "./models"):
        """
        初始化模型管理器
        
        Args:
            models_dir: 模型保存根目录
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.production_dir = self.models_dir / "production"
        self.production_dir.mkdir(exist_ok=True)
        
        # 模型注册表
        self.registry_file = self.models_dir / "registry.json"
        self.registry = self._load_registry()
    
    def _load_registry(self) -> List[Dict]:
        """加载模型注册表"""
        if self.registry_file.exists():
            with open(self.registry_file, "r") as f:
                return json.load(f)
        return []
    
    def _save_registry(self):
        """保存模型注册表"""
        with open(self.registry_file, "w") as f:
            json.dump(self.registry, f, indent=2)
    
    def save_model(
        self,
        trainer: Any,  # PPOTrainer or SACTrainer
        version: str,
        performance_metrics: Dict[str, float],
        description: str = ""
    ) -> str:
        """
        保存模型
        
        Args:
            trainer: 训练器实例
            version: 版本号（例如 "1.0"）
            performance_metrics: 性能指标（sharpe, max_dd, total_return等）
            description: 描述信息
        
        Returns:
            模型ID
        """
        # 生成模型ID
        algorithm = "ppo" if isinstance(trainer, PPOTrainer) else "sac"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_id = f"{algorithm}_v{version}_{timestamp}"
        
        # 创建模型目录
        model_dir = self.models_dir / model_id
        model_dir.mkdir(exist_ok=True)
        
        # 保存模型文件
        model_path = model_dir / "model.zip"
        trainer.save(str(model_path))
        
        # 保存元数据
        metadata = ModelMetadata(
            model_id=model_id,
            algorithm=algorithm.upper(),
            version=version,
            created_at=datetime.now(),
            trained_timesteps=trainer.model.num_timesteps,
            performance_metrics=performance_metrics,
            hyperparameters=self._extract_hyperparameters(trainer),
            description=description
        )
        
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)
        
        # 更新注册表
        self.registry.append(metadata.to_dict())
        self._save_registry()
        
        print(f"模型已保存: {model_id}")
        return model_id
    
    def _extract_hyperparameters(self, trainer: Any) -> Dict[str, Any]:
        """提取超参数"""
        if isinstance(trainer, PPOTrainer):
            return {
                "learning_rate": trainer.model.learning_rate,
                "n_steps": trainer.model.n_steps,
                "batch_size": trainer.model.batch_size,
                "n_epochs": trainer.model.n_epochs,
                "gamma": trainer.model.gamma,
                "gae_lambda": trainer.model.gae_lambda,
                "clip_range": trainer.model.clip_range,
                "ent_coef": trainer.model.ent_coef
            }
        elif isinstance(trainer, SACTrainer):
            return {
                "learning_rate": trainer.model.learning_rate,
                "buffer_size": trainer.model.buffer_size,
                "batch_size": trainer.model.batch_size,
                "gamma": trainer.model.gamma,
                "tau": trainer.model.tau,
                "ent_coef": str(trainer.model.ent_coef)
            }
        return {}
    
    def load_model(
        self,
        model_id: str,
        env: TradingEnv
    ) -> Any:
        """
        加载模型
        
        Args:
            model_id: 模型ID
            env: 交易环境
        
        Returns:
            训练器实例
        """
        model_dir = self.models_dir / model_id
        if not model_dir.exists():
            raise FileNotFoundError(f"模型不存在: {model_id}")
        
        # 读取元数据
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, "r") as f:
            metadata = ModelMetadata.from_dict(json.load(f))
        
        # 根据算法加载对应的训练器
        model_path = model_dir / "model.zip"
        if metadata.algorithm == "PPO":
            trainer = PPOTrainer(env=env, verbose=0)
            trainer.load(str(model_path))
        elif metadata.algorithm == "SAC":
            trainer = SACTrainer(env=env, verbose=0)
            trainer.load(str(model_path))
        else:
            raise ValueError(f"未知算法: {metadata.algorithm}")
        
        print(f"模型已加载: {model_id}")
        return trainer
    
    def list_models(
        self,
        algorithm: Optional[str] = None,
        sort_by: str = "created_at"
    ) -> List[ModelMetadata]:
        """
        列出所有模型
        
        Args:
            algorithm: 过滤算法（"PPO" or "SAC"）
            sort_by: 排序字段（"created_at", "version", "sharpe_ratio"）
        
        Returns:
            模型元数据列表
        """
        models = [ModelMetadata.from_dict(m) for m in self.registry]
        
        # 过滤算法
        if algorithm:
            models = [m for m in models if m.algorithm == algorithm.upper()]
        
        # 排序
        if sort_by == "created_at":
            models.sort(key=lambda m: m.created_at, reverse=True)
        elif sort_by == "version":
            models.sort(key=lambda m: m.version, reverse=True)
        elif sort_by == "sharpe_ratio":
            models.sort(key=lambda m: m.performance_metrics.get("sharpe_ratio", 0), reverse=True)
        
        return models
    
    def get_best_model(
        self,
        metric: str = "sharpe_ratio",
        algorithm: Optional[str] = None
    ) -> Optional[ModelMetadata]:
        """
        获取最佳模型
        
        Args:
            metric: 评估指标（"sharpe_ratio", "total_return", "max_drawdown"）
            algorithm: 过滤算法
        
        Returns:
            最佳模型元数据
        """
        models = self.list_models(algorithm=algorithm)
        if not models:
            return None
        
        # 根据指标排序
        if metric == "max_drawdown":
            # 回撤越小越好
            best_model = min(models, key=lambda m: abs(m.performance_metrics.get(metric, float('inf'))))
        else:
            # 其他指标越大越好
            best_model = max(models, key=lambda m: m.performance_metrics.get(metric, 0))
        
        return best_model
    
    def promote_to_production(self, model_id: str):
        """
        提升模型到生产环境
        
        Args:
            model_id: 模型ID
        """
        model_dir = self.models_dir / model_id
        if not model_dir.exists():
            raise FileNotFoundError(f"模型不存在: {model_id}")
        
        # 保存当前生产模型为previous
        current_link = self.production_dir / "current_model"
        previous_link = self.production_dir / "previous_model"
        
        if current_link.exists():
            # 删除旧的previous链接
            if previous_link.exists():
                previous_link.unlink()
            # 当前模型降级为previous
            current_target = current_link.resolve()
            if current_target.exists():
                previous_link.symlink_to(current_target)
            current_link.unlink()
        
        # 创建新的current链接
        current_link.symlink_to(model_dir.resolve())
        
        print(f"模型已提升到生产环境: {model_id}")
    
    def rollback_production(self):
        """回滚生产模型到上一个版本"""
        current_link = self.production_dir / "current_model"
        previous_link = self.production_dir / "previous_model"
        
        if not previous_link.exists():
            raise RuntimeError("没有可回滚的模型")
        
        # 当前模型删除
        if current_link.exists():
            current_link.unlink()
        
        # previous提升为current
        previous_target = previous_link.resolve()
        current_link.symlink_to(previous_target)
        previous_link.unlink()
        
        print(f"已回滚到模型: {previous_target.name}")
    
    def get_production_model(self) -> Optional[str]:
        """获取当前生产模型ID"""
        current_link = self.production_dir / "current_model"
        if not current_link.exists():
            return None
        
        target = current_link.resolve()
        return target.name
    
    def compare_models(
        self,
        model_id1: str,
        model_id2: str
    ) -> Dict[str, Any]:
        """
        比较两个模型的性能
        
        Args:
            model_id1: 模型1 ID
            model_id2: 模型2 ID
        
        Returns:
            比较结果
        """
        # 读取两个模型的元数据
        metadata1_path = self.models_dir / model_id1 / "metadata.json"
        metadata2_path = self.models_dir / model_id2 / "metadata.json"
        
        with open(metadata1_path, "r") as f:
            metadata1 = ModelMetadata.from_dict(json.load(f))
        with open(metadata2_path, "r") as f:
            metadata2 = ModelMetadata.from_dict(json.load(f))
        
        # 比较性能指标
        comparison = {
            "model1": model_id1,
            "model2": model_id2,
            "metrics_comparison": {}
        }
        
        for metric in metadata1.performance_metrics.keys():
            val1 = metadata1.performance_metrics.get(metric, 0)
            val2 = metadata2.performance_metrics.get(metric, 0)
            
            comparison["metrics_comparison"][metric] = {
                "model1": val1,
                "model2": val2,
                "difference": val2 - val1,
                "improvement_pct": ((val2 - val1) / val1 * 100) if val1 != 0 else 0
            }
        
        return comparison
    
    def delete_model(self, model_id: str):
        """删除模型"""
        model_dir = self.models_dir / model_id
        if not model_dir.exists():
            raise FileNotFoundError(f"模型不存在: {model_id}")
        
        # 删除目录
        shutil.rmtree(model_dir)
        
        # 更新注册表
        self.registry = [m for m in self.registry if m["model_id"] != model_id]
        self._save_registry()
        
        print(f"模型已删除: {model_id}")


if __name__ == "__main__":
    # 示例：模型管理
    
    manager = ModelManager(models_dir="./models")
    
    # 列出所有模型
    models = manager.list_models()
    print(f"共有 {len(models)} 个模型")
    
    for model in models:
        print(f"- {model.model_id}: Sharpe={model.performance_metrics.get('sharpe_ratio', 0):.2f}")
    
    # 获取最佳模型
    best_model = manager.get_best_model(metric="sharpe_ratio")
    if best_model:
        print(f"\n最佳模型（Sharpe Ratio）: {best_model.model_id}")
    
    # 获取生产模型
    prod_model = manager.get_production_model()
    if prod_model:
        print(f"当前生产模型: {prod_model}")

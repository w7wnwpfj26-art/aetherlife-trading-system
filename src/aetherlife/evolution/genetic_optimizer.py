"""
遗传算法优化器 (Genetic Algorithm Optimizer)

使用遗传算法优化策略参数:
- 种群管理
- 适应度评估
- 选择、交叉、变异
- 精英保留
"""

from typing import List, Dict, Any, Callable, Tuple
from dataclasses import dataclass
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger("aetherlife.evolution.genetic")


@dataclass
class Individual:
    """个体（一组策略参数）"""
    genes: Dict[str, Any]  # 参数基因
    fitness: float = 0.0  # 适应度
    generation: int = 0  # 代数
    id: str = ""
    
    def __post_init__(self):
        if not self.id:
            self.id = f"ind_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


@dataclass
class GeneConfig:
    """基因配置"""
    name: str
    type: str  # "int", "float", "choice"
    min_value: float = None
    max_value: float = None
    choices: List[Any] = None
    mutation_rate: float = 0.1
    mutation_std: float = 0.2  # 突变标准差（相对）


class GeneticOptimizer:
    """
    遗传算法优化器
    
    核心流程:
    1. 初始化种群
    2. 评估适应度（回测）
    3. 选择父代（轮盘赌/锦标赛）
    4. 交叉生成子代
    5. 变异
    6. 精英保留
    7. 重复2-6
    """
    
    def __init__(
        self,
        gene_configs: List[GeneConfig],
        fitness_func: Callable[[Dict[str, Any]], float],
        population_size: int = 50,
        elite_size: int = 5,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        tournament_size: int = 3,
        max_generations: int = 100,
        target_fitness: float = None,
        verbose: int = 1
    ):
        """
        初始化遗传算法优化器
        
        Args:
            gene_configs: 基因配置列表
            fitness_func: 适应度函数（参数 → Sharpe Ratio）
            population_size: 种群大小
            elite_size: 精英个体数量
            mutation_rate: 变异率
            crossover_rate: 交叉率
            tournament_size: 锦标赛选择大小
            max_generations: 最大代数
            target_fitness: 目标适应度（达到后停止）
            verbose: 日志详细程度
        """
        self.gene_configs = {gc.name: gc for gc in gene_configs}
        self.fitness_func = fitness_func
        self.population_size = population_size
        self.elite_size = elite_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.tournament_size = tournament_size
        self.max_generations = max_generations
        self.target_fitness = target_fitness
        self.verbose = verbose
        
        # 种群
        self.population: List[Individual] = []
        self.best_individual: Individual = None
        self.generation = 0
        
        # 历史记录
        self.history = {
            "best_fitness": [],
            "avg_fitness": [],
            "generations": []
        }
    
    def initialize_population(self):
        """初始化种群"""
        self.population = []
        for _ in range(self.population_size):
            genes = self._random_genes()
            individual = Individual(genes=genes, generation=0)
            self.population.append(individual)
        
        if self.verbose >= 1:
            print(f"✅ 初始化种群: {self.population_size}个个体")
    
    def _random_genes(self) -> Dict[str, Any]:
        """生成随机基因"""
        genes = {}
        for name, config in self.gene_configs.items():
            if config.type == "int":
                genes[name] = np.random.randint(config.min_value, config.max_value + 1)
            elif config.type == "float":
                genes[name] = np.random.uniform(config.min_value, config.max_value)
            elif config.type == "choice":
                genes[name] = np.random.choice(config.choices)
            else:
                raise ValueError(f"不支持的基因类型: {config.type}")
        return genes
    
    def evaluate_population(self):
        """评估种群适应度"""
        for individual in self.population:
            if individual.fitness == 0.0:  # 未评估过
                try:
                    individual.fitness = self.fitness_func(individual.genes)
                except Exception as e:
                    logger.warning(f"适应度评估失败: {e}")
                    individual.fitness = -np.inf
        
        # 排序
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        # 更新最优个体
        if not self.best_individual or self.population[0].fitness > self.best_individual.fitness:
            self.best_individual = self.population[0]
        
        # 记录历史
        self.history["best_fitness"].append(self.population[0].fitness)
        self.history["avg_fitness"].append(np.mean([ind.fitness for ind in self.population]))
        self.history["generations"].append(self.generation)
    
    def select_parents(self) -> Tuple[Individual, Individual]:
        """选择父代（锦标赛选择）"""
        def tournament_select() -> Individual:
            candidates = np.random.choice(self.population, self.tournament_size, replace=False)
            return max(candidates, key=lambda x: x.fitness)
        
        parent1 = tournament_select()
        parent2 = tournament_select()
        return parent1, parent2
    
    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """交叉（单点交叉）"""
        if np.random.rand() > self.crossover_rate:
            # 不交叉，直接复制
            return (
                Individual(genes=parent1.genes.copy(), generation=self.generation + 1),
                Individual(genes=parent2.genes.copy(), generation=self.generation + 1)
            )
        
        # 单点交叉
        gene_names = list(self.gene_configs.keys())
        crossover_point = np.random.randint(1, len(gene_names))
        
        child1_genes = {}
        child2_genes = {}
        
        for i, name in enumerate(gene_names):
            if i < crossover_point:
                child1_genes[name] = parent1.genes[name]
                child2_genes[name] = parent2.genes[name]
            else:
                child1_genes[name] = parent2.genes[name]
                child2_genes[name] = parent1.genes[name]
        
        return (
            Individual(genes=child1_genes, generation=self.generation + 1),
            Individual(genes=child2_genes, generation=self.generation + 1)
        )
    
    def mutate(self, individual: Individual):
        """变异"""
        for name, config in self.gene_configs.items():
            if np.random.rand() < (config.mutation_rate or self.mutation_rate):
                if config.type == "int":
                    # 高斯变异
                    std = (config.max_value - config.min_value) * config.mutation_std
                    new_value = int(individual.genes[name] + np.random.randn() * std)
                    individual.genes[name] = np.clip(new_value, config.min_value, config.max_value)
                
                elif config.type == "float":
                    # 高斯变异
                    std = (config.max_value - config.min_value) * config.mutation_std
                    new_value = individual.genes[name] + np.random.randn() * std
                    individual.genes[name] = np.clip(new_value, config.min_value, config.max_value)
                
                elif config.type == "choice":
                    # 随机选择
                    individual.genes[name] = np.random.choice(config.choices)
    
    def evolve_generation(self):
        """进化一代"""
        # 1. 评估适应度
        self.evaluate_population()
        
        # 2. 精英保留
        new_population = self.population[:self.elite_size]
        
        # 3. 生成子代
        while len(new_population) < self.population_size:
            # 选择
            parent1, parent2 = self.select_parents()
            
            # 交叉
            child1, child2 = self.crossover(parent1, parent2)
            
            # 变异
            self.mutate(child1)
            self.mutate(child2)
            
            new_population.extend([child1, child2])
        
        # 4. 截断到种群大小
        self.population = new_population[:self.population_size]
        self.generation += 1
        
        # 5. 打印进度
        if self.verbose >= 1:
            best_fitness = self.history["best_fitness"][-1]
            avg_fitness = self.history["avg_fitness"][-1]
            print(f"Generation {self.generation:3d} | Best: {best_fitness:.4f} | Avg: {avg_fitness:.4f}")
    
    def optimize(self) -> Individual:
        """
        运行优化
        
        Returns:
            最优个体
        """
        if self.verbose >= 1:
            print(f"\n{'='*60}")
            print("开始遗传算法优化")
            print(f"种群大小: {self.population_size}")
            print(f"最大代数: {self.max_generations}")
            print(f"基因数量: {len(self.gene_configs)}")
            print(f"{'='*60}\n")
        
        # 初始化
        self.initialize_population()
        
        # 进化
        for gen in range(self.max_generations):
            self.evolve_generation()
            
            # 检查是否达到目标
            if self.target_fitness and self.best_individual.fitness >= self.target_fitness:
                if self.verbose >= 1:
                    print(f"\n✅ 达到目标适应度 {self.target_fitness:.4f}，提前停止")
                break
        
        if self.verbose >= 1:
            print(f"\n{'='*60}")
            print("优化完成")
            print(f"最优适应度: {self.best_individual.fitness:.4f}")
            print(f"最优参数:")
            for name, value in self.best_individual.genes.items():
                print(f"  {name}: {value}")
            print(f"{'='*60}\n")
        
        return self.best_individual
    
    def get_best_parameters(self) -> Dict[str, Any]:
        """获取最优参数"""
        return self.best_individual.genes if self.best_individual else {}


if __name__ == "__main__":
    # 示例：优化RSI策略参数
    
    # 定义基因配置
    gene_configs = [
        GeneConfig(
            name="rsi_period",
            type="int",
            min_value=5,
            max_value=50,
            mutation_rate=0.2
        ),
        GeneConfig(
            name="rsi_oversold",
            type="int",
            min_value=10,
            max_value=40,
            mutation_rate=0.1
        ),
        GeneConfig(
            name="rsi_overbought",
            type="int",
            min_value=60,
            max_value=90,
            mutation_rate=0.1
        ),
        GeneConfig(
            name="position_size",
            type="float",
            min_value=0.1,
            max_value=1.0,
            mutation_rate=0.1,
            mutation_std=0.1
        ),
        GeneConfig(
            name="stop_loss",
            type="float",
            min_value=0.01,
            max_value=0.1,
            mutation_rate=0.1
        )
    ]
    
    # 定义适应度函数（模拟回测）
    def fitness_func(params: Dict[str, Any]) -> float:
        """模拟适应度函数"""
        # 实际应用中，这里应该运行完整回测
        # 这里简化为基于参数的启发式评分
        rsi_period = params["rsi_period"]
        rsi_oversold = params["rsi_oversold"]
        rsi_overbought = params["rsi_overbought"]
        
        # 模拟：期间越短、阈值越极端 → 夏普越低
        score = 1.0
        score -= abs(rsi_period - 14) * 0.01  # 偏离14惩罚
        score -= abs(rsi_oversold - 30) * 0.005
        score -= abs(rsi_overbought - 70) * 0.005
        score += np.random.randn() * 0.1  # 添加噪声
        
        return max(score, 0)
    
    # 创建优化器
    optimizer = GeneticOptimizer(
        gene_configs=gene_configs,
        fitness_func=fitness_func,
        population_size=30,
        elite_size=3,
        max_generations=20,
        target_fitness=1.5,
        verbose=1
    )
    
    # 运行优化
    best = optimizer.optimize()
    
    print(f"\n最优参数组合:")
    for name, value in best.genes.items():
        print(f"  {name}: {value}")

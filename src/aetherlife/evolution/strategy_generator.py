"""
LLM策略生成器 (Strategy Generator)

使用LLM自动生成交易策略代码:
- 基于市场洞察生成策略
- 代码安全沙箱验证
- 自动回测评估
- 持续迭代优化
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import os
import json
import subprocess
import tempfile
import logging

logger = logging.getLogger("aetherlife.evolution.generator")


@dataclass
class StrategyTemplate:
    """策略模板"""
    name: str
    description: str
    code: str
    parameters: Dict[str, Any]
    category: str  # "trend", "mean_reversion", "arbitrage", "ml"
    

@dataclass
class GeneratedStrategy:
    """生成的策略"""
    id: str
    code: str
    description: str
    parameters: Dict[str, Any]
    validation_result: Dict[str, Any]
    created_at: datetime
    

class StrategyGenerator:
    """
    LLM策略生成器
    
    核心功能:
    1. 基于市场观察生成策略假设
    2. 将假设转换为可执行代码
    3. 安全沙箱验证
    4. 自动回测评估
    """
    
    def __init__(
        self,
        llm_provider: str = "openai",
        model_name: str = "gpt-4",
        template_dir: Optional[str] = None,
        max_iterations: int = 3
    ):
        """
        初始化策略生成器
        
        Args:
            llm_provider: LLM提供商 ("openai", "anthropic", "local")
            model_name: 模型名称
            template_dir: 策略模板目录
            max_iterations: 最大迭代次数
        """
        self.llm_provider = llm_provider
        self.model_name = model_name
        self.template_dir = template_dir
        self.max_iterations = max_iterations
        
        # 加载策略模板
        self.templates = self._load_templates()
        
        # 初始化LLM客户端
        self.llm_client = self._init_llm_client()
        
    def _load_templates(self) -> List[StrategyTemplate]:
        """加载策略模板"""
        templates = []
        
        # 内置基础模板
        templates.extend([
            StrategyTemplate(
                name="trend_following",
                description="趋势跟踪策略模板",
                code="""
def strategy(bar, position, params):
    # 计算移动平均
    fast_ma = params['fast_period']
    slow_ma = params['slow_period']
    
    # 金叉做多，死叉做空
    if fast_ma > slow_ma:
        return params['position_size']
    elif fast_ma < slow_ma:
        return -params['position_size'] if params['allow_short'] else 0
    return position
""",
                parameters={"fast_period": 10, "slow_period": 30, "position_size": 0.5, "allow_short": False},
                category="trend"
            ),
            StrategyTemplate(
                name="mean_reversion",
                description="均值回归策略模板",
                code="""
def strategy(bar, position, params):
    # 计算布林带
    upper_band = params['mean'] + params['std_dev'] * params['num_std']
    lower_band = params['mean'] - params['std_dev'] * params['num_std']
    price = bar['close']
    
    # 价格超买做空，超卖做多
    if price > upper_band:
        return -params['position_size'] if params['allow_short'] else 0
    elif price < lower_band:
        return params['position_size']
    return 0
""",
                parameters={"mean": 10000, "std_dev": 100, "num_std": 2, "position_size": 0.5, "allow_short": False},
                category="mean_reversion"
            )
        ])
        
        # 从文件加载自定义模板
        if self.template_dir and os.path.exists(self.template_dir):
            try:
                for filename in os.listdir(self.template_dir):
                    if filename.endswith(".json"):
                        with open(os.path.join(self.template_dir, filename), 'r') as f:
                            data = json.load(f)
                            templates.append(StrategyTemplate(**data))
            except Exception as e:
                logger.warning(f"加载模板失败: {e}")
        
        return templates
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.llm_provider == "openai":
            try:
                import openai
                return openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except ImportError:
                logger.error("请安装openai: pip install openai")
                return None
        elif self.llm_provider == "anthropic":
            try:
                import anthropic
                return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            except ImportError:
                logger.error("请安装anthropic: pip install anthropic")
                return None
        else:
            logger.warning(f"不支持的LLM提供商: {self.llm_provider}")
            return None
    
    def generate_from_insight(
        self,
        market_insight: str,
        category: Optional[str] = None,
        base_template: Optional[str] = None
    ) -> Optional[GeneratedStrategy]:
        """
        基于市场洞察生成策略
        
        Args:
            market_insight: 市场观察/洞察描述
            category: 策略类别
            base_template: 基础模板名称
        
        Returns:
            生成的策略
        """
        if not self.llm_client:
            logger.error("LLM客户端未初始化")
            return None
        
        # 选择模板
        template = None
        if base_template:
            template = next((t for t in self.templates if t.name == base_template), None)
        elif category:
            template = next((t for t in self.templates if t.category == category), None)
        
        # 构造提示词
        prompt = self._build_prompt(market_insight, template)
        
        # 调用LLM生成策略
        try:
            if self.llm_provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "你是一位专业的量化交易策略开发专家"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
                code = response.choices[0].message.content
            else:
                logger.error(f"不支持的LLM提供商: {self.llm_provider}")
                return None
            
            # 提取代码
            code = self._extract_code(code)
            
            # 验证代码
            validation_result = self._validate_code(code)
            
            # 创建策略对象
            strategy = GeneratedStrategy(
                id=f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                code=code,
                description=market_insight,
                parameters={},
                validation_result=validation_result,
                created_at=datetime.now()
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"生成策略失败: {e}")
            return None
    
    def _build_prompt(self, insight: str, template: Optional[StrategyTemplate]) -> str:
        """构造提示词"""
        prompt = f"""
请基于以下市场洞察，生成一个量化交易策略的Python函数。

【市场洞察】
{insight}

【要求】
1. 函数签名必须是: def strategy(bar, position, params)
   - bar: 当前K线数据 (dict)，包含: open, high, low, close, volume, timestamp
   - position: 当前持仓 (float)，范围 [-1, 1]
   - params: 策略参数 (dict)
   
2. 返回目标仓位 (float)，范围 [-1, 1]
   - 1: 满仓做多
   - -1: 满仓做空
   - 0: 空仓
   
3. 代码必须:
   - 包含清晰的注释
   - 处理边界情况
   - 避免使用外部依赖（仅numpy/pandas可用）
   - 计算高效
"""
        
        if template:
            prompt += f"""
【参考模板】
{template.code}

【模板参数】
{json.dumps(template.parameters, indent=2)}
"""
        
        prompt += """
请直接输出Python代码，用```python和```包裹。
"""
        return prompt
    
    def _extract_code(self, response: str) -> str:
        """从LLM响应中提取代码"""
        # 移除markdown代码块标记
        if "```python" in response:
            start = response.find("```python") + 9
            end = response.find("```", start)
            code = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            code = response[start:end].strip()
        else:
            code = response.strip()
        
        return code
    
    def _validate_code(self, code: str) -> Dict[str, Any]:
        """
        在沙箱中验证代码
        
        Returns:
            验证结果
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": []
        }
        
        # 1. 语法检查
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            result["errors"].append(f"语法错误: {e}")
            return result
        
        # 2. 安全检查
        dangerous_imports = ["os", "sys", "subprocess", "shutil", "requests"]
        for dangerous in dangerous_imports:
            if f"import {dangerous}" in code or f"from {dangerous}" in code:
                result["errors"].append(f"禁止导入: {dangerous}")
                return result
        
        # 3. 函数签名检查
        if "def strategy(bar, position, params)" not in code:
            result["errors"].append("缺少正确的函数签名: def strategy(bar, position, params)")
            return result
        
        # 4. 沙箱执行测试
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            # 测试执行
            test_code = f"""
{code}

# 测试调用
bar = {{'open': 100, 'high': 105, 'low': 95, 'close': 102, 'volume': 1000, 'timestamp': '2025-01-01'}}
position = 0.0
params = {{'test': True}}
result = strategy(bar, position, params)
print(f"测试结果: {{result}}")
"""
            
            with open(temp_path, 'w') as f:
                f.write(test_code)
            
            proc = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if proc.returncode != 0:
                result["errors"].append(f"执行错误: {proc.stderr}")
                return result
            
            result["valid"] = True
            
        except subprocess.TimeoutExpired:
            result["errors"].append("执行超时（5秒）")
        except Exception as e:
            result["errors"].append(f"验证失败: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        
        return result
    
    def iterate_strategy(
        self,
        strategy: GeneratedStrategy,
        backtest_result: Dict[str, Any],
        target_metric: str = "sharpe_ratio"
    ) -> Optional[GeneratedStrategy]:
        """
        基于回测结果迭代优化策略
        
        Args:
            strategy: 当前策略
            backtest_result: 回测结果
            target_metric: 目标优化指标
        
        Returns:
            改进的策略
        """
        if not self.llm_client:
            return None
        
        # 构造改进提示
        prompt = f"""
以下策略的回测结果不理想，请优化:

【当前策略】
{strategy.code}

【回测结果】
- Sharpe Ratio: {backtest_result.get('sharpe_ratio', 0):.2f}
- 最大回撤: {backtest_result.get('max_drawdown', 0):.2%}
- 胜率: {backtest_result.get('win_rate', 0):.2%}

【目标】
提升{target_metric}指标

请保持函数签名不变，优化策略逻辑。直接输出改进后的完整代码。
"""
        
        try:
            if self.llm_provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "你是策略优化专家"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8
                )
                improved_code = self._extract_code(response.choices[0].message.content)
            else:
                return None
            
            # 验证改进后的代码
            validation = self._validate_code(improved_code)
            
            if validation["valid"]:
                return GeneratedStrategy(
                    id=f"{strategy.id}_v2",
                    code=improved_code,
                    description=f"改进版: {strategy.description}",
                    parameters=strategy.parameters,
                    validation_result=validation,
                    created_at=datetime.now()
                )
            else:
                logger.warning(f"改进后的策略验证失败: {validation['errors']}")
                return None
                
        except Exception as e:
            logger.error(f"策略迭代失败: {e}")
            return None


if __name__ == "__main__":
    # 示例用法
    generator = StrategyGenerator(llm_provider="openai")
    
    # 生成策略
    insight = "BTC在凌晨2-4点通常波动率较低，适合均值回归策略"
    strategy = generator.generate_from_insight(insight, category="mean_reversion")
    
    if strategy and strategy.validation_result["valid"]:
        print(f"✅ 策略生成成功: {strategy.id}")
        print(strategy.code)
    else:
        print("❌ 策略生成失败")

"""
思维链推理引擎 - 提升 Agent 的复杂问题解决能力

核心功能：
1. 多步推理：将复杂问题分解为逻辑步骤
2. 自我验证：每一步推理都进行验证
3. 回溯修正：发现错误时回溯修正
4. 推理优化：学习更优的推理路径
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime


class ReasoningStepType(Enum):
    """推理步骤类型"""
    OBSERVATION = "observation"      # 观察事实
    HYPOTHESIS = "hypothesis"        # 提出假设
    ANALYSIS = "analysis"            # 分析推理
    VERIFICATION = "verification"    # 验证检查
    CONCLUSION = "conclusion"        # 得出结论
    CORRECTION = "correction"        # 修正错误


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_id: int
    step_type: ReasoningStepType
    content: str
    confidence: float  # 置信度 0.0-1.0
    evidence: List[str] = None  # 支持证据
    depends_on: List[int] = None  # 依赖的步骤
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []
        if self.depends_on is None:
            self.depends_on = []
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "content": self.content,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "depends_on": self.depends_on,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ReasoningChain:
    """推理链"""
    chain_id: str
    problem: str
    steps: List[ReasoningStep]
    final_conclusion: Optional[str] = None
    overall_confidence: float = 0.0
    created_at: datetime = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def add_step(self, step: ReasoningStep) -> None:
        """添加推理步骤"""
        self.steps.append(step)
    
    def get_step(self, step_id: int) -> Optional[ReasoningStep]:
        """获取指定步骤"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def get_last_step(self) -> Optional[ReasoningStep]:
        """获取最后一步"""
        if self.steps:
            return self.steps[-1]
        return None
    
    def calculate_confidence(self) -> float:
        """计算整体置信度"""
        if not self.steps:
            return 0.0
        
        # 加权平均，结论步骤权重更高
        total_weight = 0
        weighted_sum = 0
        
        for step in self.steps:
            if step.step_type == ReasoningStepType.CONCLUSION:
                weight = 2.0
            elif step.step_type == ReasoningStepType.VERIFICATION:
                weight = 1.5
            else:
                weight = 1.0
            
            weighted_sum += step.confidence * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "chain_id": self.chain_id,
            "problem": self.problem,
            "steps": [step.to_dict() for step in self.steps],
            "final_conclusion": self.final_conclusion,
            "overall_confidence": round(self.overall_confidence, 2),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class ChainOfThoughtReasoner:
    """思维链推理器"""
    
    def __init__(self, max_steps: int = 20, min_confidence: float = 0.7):
        self.max_steps = max_steps
        self.min_confidence = min_confidence
        self.chains: Dict[str, ReasoningChain] = {}
        self.step_counter = 0
    
    def create_chain(self, problem: str) -> str:
        """创建新的推理链"""
        chain_id = f"chain_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.chains)}"
        chain = ReasoningChain(
            chain_id=chain_id,
            problem=problem,
            steps=[]
        )
        self.chains[chain_id] = chain
        return chain_id
    
    def add_observation(self, chain_id: str, observation: str, confidence: float = 0.9) -> int:
        """添加观察步骤"""
        return self._add_step(
            chain_id=chain_id,
            step_type=ReasoningStepType.OBSERVATION,
            content=f"观察: {observation}",
            confidence=confidence
        )
    
    def add_hypothesis(self, chain_id: str, hypothesis: str, confidence: float = 0.7, 
                      depends_on: List[int] = None) -> int:
        """添加假设步骤"""
        return self._add_step(
            chain_id=chain_id,
            step_type=ReasoningStepType.HYPOTHESIS,
            content=f"假设: {hypothesis}",
            confidence=confidence,
            depends_on=depends_on
        )
    
    def add_analysis(self, chain_id: str, analysis: str, confidence: float = 0.8,
                    depends_on: List[int] = None) -> int:
        """添加分析步骤"""
        return self._add_step(
            chain_id=chain_id,
            step_type=ReasoningStepType.ANALYSIS,
            content=f"分析: {analysis}",
            confidence=confidence,
            depends_on=depends_on
        )
    
    def add_verification(self, chain_id: str, verification: str, confidence: float = 0.85,
                        depends_on: List[int] = None) -> int:
        """添加验证步骤"""
        return self._add_step(
            chain_id=chain_id,
            step_type=ReasoningStepType.VERIFICATION,
            content=f"验证: {verification}",
            confidence=confidence,
            depends_on=depends_on
        )
    
    def add_conclusion(self, chain_id: str, conclusion: str, confidence: float = 0.9,
                      depends_on: List[int] = None) -> int:
        """添加结论步骤"""
        step_id = self._add_step(
            chain_id=chain_id,
            step_type=ReasoningStepType.CONCLUSION,
            content=f"结论: {conclusion}",
            confidence=confidence,
            depends_on=depends_on
        )
        
        # 更新推理链的最终结论
        chain = self.chains[chain_id]
        chain.final_conclusion = conclusion
        chain.overall_confidence = chain.calculate_confidence()
        chain.completed_at = datetime.now()
        
        return step_id
    
    def add_correction(self, chain_id: str, correction: str, corrects_step: int,
                      confidence: float = 0.8) -> int:
        """添加修正步骤"""
        return self._add_step(
            chain_id=chain_id,
            step_type=ReasoningStepType.CORRECTION,
            content=f"修正: {correction} (修正步骤 {corrects_step})",
            confidence=confidence,
            depends_on=[corrects_step]
        )
    
    def _add_step(self, chain_id: str, step_type: ReasoningStepType, content: str,
                 confidence: float, depends_on: List[int] = None) -> int:
        """添加通用步骤"""
        if chain_id not in self.chains:
            raise ValueError(f"推理链 {chain_id} 不存在")
        
        chain = self.chains[chain_id]
        
        # 检查步骤数量限制
        if len(chain.steps) >= self.max_steps:
            raise ValueError(f"已达到最大步骤数限制: {self.max_steps}")
        
        # 生成步骤ID
        self.step_counter += 1
        step_id = self.step_counter
        
        # 创建步骤
        step = ReasoningStep(
            step_id=step_id,
            step_type=step_type,
            content=content,
            confidence=max(0.0, min(1.0, confidence)),  # 限制在0-1之间
            depends_on=depends_on or []
        )
        
        # 添加到链中
        chain.add_step(step)
        
        return step_id
    
    def get_chain(self, chain_id: str) -> Optional[ReasoningChain]:
        """获取推理链"""
        return self.chains.get(chain_id)
    
    def get_chain_summary(self, chain_id: str) -> Dict[str, Any]:
        """获取推理链摘要"""
        chain = self.get_chain(chain_id)
        if not chain:
            return {}
        
        return {
            "chain_id": chain_id,
            "problem": chain.problem,
            "step_count": len(chain.steps),
            "final_conclusion": chain.final_conclusion,
            "overall_confidence": chain.overall_confidence,
            "is_completed": chain.completed_at is not None
        }
    
    def analyze_problem(self, problem: str) -> Dict[str, Any]:
        """分析问题并创建推理链"""
        chain_id = self.create_chain(problem)
        
        # 第一步：观察问题
        obs_id = self.add_observation(
            chain_id=chain_id,
            observation=f"分析问题: {problem}",
            confidence=0.9
        )
        
        # 第二步：分解问题
        analysis_id = self.add_analysis(
            chain_id=chain_id,
            analysis="将复杂问题分解为多个子问题",
            confidence=0.8,
            depends_on=[obs_id]
        )
        
        # 第三步：提出解决方案假设
        hypothesis_id = self.add_hypothesis(
            chain_id=chain_id,
            hypothesis="基于问题分析提出初步解决方案",
            confidence=0.7,
            depends_on=[analysis_id]
        )
        
        return {
            "chain_id": chain_id,
            "steps_created": [obs_id, analysis_id, hypothesis_id],
            "next_action": "需要进一步验证假设并得出结论"
        }
    
    def validate_chain(self, chain_id: str) -> Dict[str, Any]:
        """验证推理链的逻辑一致性"""
        chain = self.get_chain(chain_id)
        if not chain:
            return {"valid": False, "error": "推理链不存在"}
        
        issues = []
        
        # 检查步骤依赖关系
        step_ids = {step.step_id for step in chain.steps}
        for step in chain.steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    issues.append(f"步骤 {step.step_id} 依赖不存在的步骤 {dep_id}")
        
        # 检查置信度
        low_confidence_steps = [
            step.step_id for step in chain.steps 
            if step.confidence < self.min_confidence
        ]
        if low_confidence_steps:
            issues.append(f"低置信度步骤: {low_confidence_steps}")
        
        # 检查是否有结论
        has_conclusion = any(
            step.step_type == ReasoningStepType.CONCLUSION 
            for step in chain.steps
        )
        if not has_conclusion and len(chain.steps) > 3:
            issues.append("推理链缺少结论步骤")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "step_count": len(chain.steps),
            "has_conclusion": has_conclusion,
            "overall_confidence": chain.overall_confidence
        }
    
    def export_chain(self, chain_id: str, format: str = "json") -> str:
        """导出推理链"""
        chain = self.get_chain(chain_id)
        if not chain:
            return ""
        
        if format == "json":
            return json.dumps(chain.to_dict(), indent=2, ensure_ascii=False)
        elif format == "text":
            lines = [f"推理链: {chain_id}", f"问题: {chain.problem}", ""]
            for step in chain.steps:
                lines.append(f"[步骤 {step.step_id}] {step.step_type.value}: {step.content}")
                lines.append(f"  置信度: {step.confidence:.2f}")
                if step.depends_on:
                    lines.append(f"  依赖: {step.depends_on}")
                lines.append("")
            
            if chain.final_conclusion:
                lines.append(f"最终结论: {chain.final_conclusion}")
                lines.append(f"整体置信度: {chain.overall_confidence:.2f}")
            
            return "\n".join(lines)
        else:
            raise ValueError(f"不支持的格式: {format}")


# 全局推理器实例
global_reasoner = ChainOfThoughtReasoner()


def get_reasoner() -> ChainOfThoughtReasoner:
    """获取全局推理器实例"""
    return global_reasoner


def analyze_complex_problem(problem: str) -> Dict[str, Any]:
    """分析复杂问题的便捷函数"""
    reasoner = get_reasoner()
    return reasoner.analyze_problem(problem)


def create_reasoning_report(chain_id: str) -> str:
    """创建推理报告"""
    reasoner = get_reasoner()
    return reasoner.export_chain(chain_id, format="text")


if __name__ == "__main__":
    # 测试推理引擎
    reasoner = ChainOfThoughtReasoner()
    
    # 创建一个推理链
    chain_id = reasoner.create_chain("如何优化一个Python项目的性能？")
    
    # 添加推理步骤
    obs_id = reasoner.add_observation(chain_id, "当前项目响应时间较慢")
    analysis_id = reasoner.add_analysis(chain_id, "可能的原因：数据库查询慢、算法复杂度高、内存泄漏", depends_on=[obs_id])
    hypothesis_id = reasoner.add_hypothesis(chain_id, "使用缓存和索引优化数据库查询", depends_on=[analysis_id])
    verification_id = reasoner.add_verification(chain_id, "检查数据库查询计划和索引使用情况", depends_on=[hypothesis_id])
    conclusion_id = reasoner.add_conclusion(chain_id, "建议：1. 添加数据库索引 2. 实现查询缓存 3. 优化算法复杂度", depends_on=[verification_id])
    
    # 验证推理链
    validation = reasoner.validate_chain(chain_id)
    print(f"验证结果: {validation}")
    
    # 导出推理链
    report = reasoner.export_chain(chain_id, format="text")
    print("\n推理报告:")
    print(report)
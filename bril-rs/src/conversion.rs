use std::fmt::Display;

use crate::{
    AbstractArgument, AbstractCode, AbstractFunction, AbstractInstruction, AbstractProgram,
    AbstractType, Argument, Code, EffectOps, Function, Instruction, Position, Program, Type,
    ValueOps,
};

use thiserror::Error;

// This is a nifty trick to supply a global value for pos when it is not defined
#[cfg(not(feature = "position"))]
#[allow(non_upper_case_globals)]
const pos: Option<Position> = None;

// Having the #[error(...)] for all variants derives the Display trait as well
#[derive(Error, Debug)]
#[allow(clippy::module_name_repetitions)]
pub enum ConversionError {
    #[error("Expected a primitive type like int or bool, found {0}")]
    InvalidPrimitive(String),

    #[error("Expected a parameterized type like ptr, found {0}<{1}>")]
    InvalidParameterized(String, String),

    #[error("Expected an value operation, found {0}")]
    InvalidValueOps(String),

    #[error("Expected an effect operation, found {0}")]
    InvalidEffectOps(String),

    #[error("Missing type signature")]
    MissingType,
}

impl ConversionError {
    pub fn add_pos(self, pos_var: Option<Position>) -> PositionalConversionError {
        match self {
            //Self::PositionalConversionErrorConversion(e) => e,
            _ => PositionalConversionError {
                e: Box::new(self),
                pos: pos_var,
            },
        }
    }
}

#[derive(Error, Debug)]
pub struct PositionalConversionError {
    e: Box<ConversionError>,
    pos: Option<Position>,
}

impl PositionalConversionError {
    pub fn new(e: ConversionError) -> Self {
        Self {
            e: Box::new(e),
            pos: None,
        }
    }
}

impl Display for PositionalConversionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            #[cfg(feature = "position")]
            PositionalConversionError { e, pos: Some(pos) } => {
                write!(f, "Line {}, Column {}: {}", pos.row, pos.col, e)
            }
            #[cfg(not(feature = "position"))]
            PositionalConversionError { e: _, pos: Some(_) } => {
                unreachable!()
            }
            PositionalConversionError { e, pos: None } => write!(f, "{}", e),
        }
    }
}

impl TryFrom<AbstractProgram> for Program {
    type Error = PositionalConversionError;
    fn try_from(AbstractProgram { functions }: AbstractProgram) -> Result<Self, Self::Error> {
        Ok(Self {
            functions: functions
                .into_iter()
                .map(std::convert::TryInto::try_into)
                .collect::<Result<Vec<Function>, _>>()?,
        })
    }
}

impl TryFrom<AbstractFunction> for Function {
    type Error = PositionalConversionError;
    fn try_from(
        AbstractFunction {
            args,
            instrs,
            name,
            return_type,
            #[cfg(feature = "position")]
            pos,
        }: AbstractFunction,
    ) -> Result<Self, Self::Error> {
        Ok(Self {
            args: args
                .into_iter()
                .map(std::convert::TryInto::try_into)
                .collect::<Result<Vec<Argument>, _>>()
                .map_err(|e| e.add_pos(pos))?,
            instrs: instrs
                .into_iter()
                .map(std::convert::TryInto::try_into)
                .collect::<Result<Vec<Code>, _>>()?,
            name,
            return_type: match return_type {
                None => None,
                Some(t) => Some(t.try_into().map_err(|e: ConversionError| e.add_pos(pos))?),
            },
            #[cfg(feature = "position")]
            pos,
        })
    }
}

impl TryFrom<AbstractArgument> for Argument {
    type Error = ConversionError;
    fn try_from(
        AbstractArgument { name, arg_type }: AbstractArgument,
    ) -> Result<Self, Self::Error> {
        Ok(Self {
            name,
            arg_type: arg_type.try_into()?,
        })
    }
}

impl TryFrom<AbstractCode> for Code {
    type Error = PositionalConversionError;
    fn try_from(c: AbstractCode) -> Result<Self, Self::Error> {
        Ok(match c {
            AbstractCode::Label {
                label,
                #[cfg(feature = "position")]
                pos,
            } => Self::Label {
                label,
                #[cfg(feature = "position")]
                pos,
            },
            AbstractCode::Instruction(i) => Self::Instruction(i.try_into()?),
        })
    }
}

impl TryFrom<AbstractInstruction> for Instruction {
    type Error = PositionalConversionError;
    fn try_from(i: AbstractInstruction) -> Result<Self, Self::Error> {
        Ok(match i {
            AbstractInstruction::Constant {
                dest,
                op,
                const_type,
                value,
                #[cfg(feature = "position")]
                pos,
            } => Self::Constant {
                dest,
                op,
                const_type: const_type
                    .try_into()
                    .map_err(|e: ConversionError| e.add_pos(pos))?,
                value,
                #[cfg(feature = "position")]
                pos,
            },
            AbstractInstruction::Value {
                args,
                dest,
                funcs,
                labels,
                op,
                op_type,
                #[cfg(feature = "position")]
                pos,
            } => Self::Value {
                args,
                dest,
                funcs,
                labels,
                op_type: op_type
                    .try_into()
                    .map_err(|e: ConversionError| e.add_pos(pos))?,
                #[cfg(feature = "position")]
                pos,
                op: match op.as_ref() {
                    "add" => ValueOps::Add,
                    "mul" => ValueOps::Mul,
                    "div" => ValueOps::Div,
                    "eq" => ValueOps::Eq,
                    "lt" => ValueOps::Lt,
                    "gt" => ValueOps::Gt,
                    "le" => ValueOps::Le,
                    "ge" => ValueOps::Ge,
                    "not" => ValueOps::Not,
                    "and" => ValueOps::And,
                    "or" => ValueOps::Or,
                    "call" => ValueOps::Call,
                    "id" => ValueOps::Id,
                    "sub" => ValueOps::Sub,
                    #[cfg(feature = "ssa")]
                    "phi" => ValueOps::Phi,
                    #[cfg(feature = "float")]
                    "fadd" => ValueOps::Fadd,
                    #[cfg(feature = "float")]
                    "fsub" => ValueOps::Fsub,
                    #[cfg(feature = "float")]
                    "fmul" => ValueOps::Fmul,
                    #[cfg(feature = "float")]
                    "fdiv" => ValueOps::Fdiv,
                    #[cfg(feature = "float")]
                    "feq" => ValueOps::Feq,
                    #[cfg(feature = "float")]
                    "flt" => ValueOps::Flt,
                    #[cfg(feature = "float")]
                    "fgt" => ValueOps::Fgt,
                    #[cfg(feature = "float")]
                    "fle" => ValueOps::Fle,
                    #[cfg(feature = "float")]
                    "fge" => ValueOps::Fge,
                    #[cfg(feature = "memory")]
                    "alloc" => ValueOps::Alloc,
                    #[cfg(feature = "memory")]
                    "load" => ValueOps::Load,
                    #[cfg(feature = "memory")]
                    "ptradd" => ValueOps::PtrAdd,
                    v => {
                        return Err(ConversionError::InvalidValueOps(v.to_string()))
                            .map_err(|e| e.add_pos(pos))
                    }
                },
            },
            AbstractInstruction::Effect {
                args,
                funcs,
                labels,
                op,
                #[cfg(feature = "position")]
                pos,
            } => Self::Effect {
                args,
                funcs,
                labels,
                #[cfg(feature = "position")]
                pos,
                op: match op.as_ref() {
                    "jmp" => EffectOps::Jump,
                    "br" => EffectOps::Branch,
                    "call" => EffectOps::Call,
                    "ret" => EffectOps::Return,
                    "print" => EffectOps::Print,
                    "nop" => EffectOps::Nop,
                    #[cfg(feature = "memory")]
                    "store" => EffectOps::Store,
                    #[cfg(feature = "memory")]
                    "free" => EffectOps::Free,
                    #[cfg(feature = "speculate")]
                    "speculate" => EffectOps::Speculate,
                    #[cfg(feature = "speculate")]
                    "commit" => EffectOps::Commit,
                    #[cfg(feature = "speculate")]
                    "guard" => EffectOps::Guard,
                    e => {
                        return Err(ConversionError::InvalidEffectOps(e.to_string()))
                            .map_err(|e| e.add_pos(pos))
                    }
                },
            },
        })
    }
}

impl TryFrom<Option<AbstractType>> for Type {
    type Error = ConversionError;

    fn try_from(value: Option<AbstractType>) -> Result<Self, Self::Error> {
        match value {
            Some(t) => t.try_into(),
            None => Err(ConversionError::MissingType),
        }
    }
}

impl TryFrom<AbstractType> for Type {
    type Error = ConversionError;
    fn try_from(value: AbstractType) -> Result<Self, Self::Error> {
        Ok(match value {
            AbstractType::Primitive(t) if t == "int" => Self::Int,
            AbstractType::Primitive(t) if t == "bool" => Self::Bool,
            #[cfg(feature = "float")]
            AbstractType::Primitive(t) if t == "float" => Type::Float,
            AbstractType::Primitive(t) => return Err(ConversionError::InvalidPrimitive(t)),
            #[cfg(feature = "memory")]
            AbstractType::Parameterized(t, ty) if t == "ptr" => {
                Type::Pointer(Box::new((*ty).try_into()?))
            }
            AbstractType::Parameterized(t, ty) => {
                return Err(ConversionError::InvalidParameterized(t, ty.to_string()))
            }
        })
    }
}
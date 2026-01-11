use pyo3::prelude::*;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyclass_enum};
use std::sync::Arc;

use crate::constants::ITEM_FIELD_NAME;
use lancedb::arrow::arrow_schema::{
    DataType as ArrowDataType, Field as ArrowField, Fields, Schema as ArrowSchema, SchemaRef as ArrowSchemaRef,
};

#[gen_stub_pyclass_enum]
#[pyclass]
#[derive(Clone)]
enum DataType {
    String,
    Int,
    Float,
}

#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone)]
pub(crate) struct Field {
    name: String,
    data_type: DataType,
    array_length: Option<usize>,
}

impl Field {
    fn to_arrow_field(&self) -> PyResult<ArrowField> {
        if let Some(length) = self.array_length {
            match self.data_type {
                DataType::String => Ok(ArrowField::new(&self.name, ArrowDataType::FixedSizeList(
                    Arc::new(ArrowField::new(ITEM_FIELD_NAME, ArrowDataType::Utf8, false)),
                    length as i32,
                ), false)),
                DataType::Int => Ok(ArrowField::new(&self.name, ArrowDataType::FixedSizeList(
                    Arc::new(ArrowField::new(ITEM_FIELD_NAME, ArrowDataType::Int64, false)),
                    length as i32,
                ), false)),
                DataType::Float => Ok(ArrowField::new(&self.name, ArrowDataType::FixedSizeList(
                    Arc::new(ArrowField::new(ITEM_FIELD_NAME, ArrowDataType::Float64, false)),
                    length as i32,
                ), false)),
            }
        } else {
            match self.data_type {
                DataType::String => Ok(ArrowField::new(&self.name, ArrowDataType::Utf8, false)),
                DataType::Int => Ok(ArrowField::new(&self.name, ArrowDataType::Int64, false)),
                DataType::Float => Ok(ArrowField::new(&self.name, ArrowDataType::Float64, false)),
            }
        }
    }

    fn into_arrow_field(self) -> PyResult<ArrowField> {
        self.to_arrow_field()
    }
}


#[gen_stub_pyclass]
#[pyclass]
pub(crate) struct SchemaDef {
    fields: Vec<Field>,
}

impl<'a, 'py> FromPyObject<'a, 'py> for SchemaDef {
    type Error = PyErr;
    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        obj.extract()
    }
}

impl SchemaDef {
    pub(crate) fn to_arrow_schema(&self) -> PyResult<ArrowSchema> {
        Ok(ArrowSchema::new(Fields::from_iter(
            self.fields
                .iter()
                .cloned()
                .map(Field::into_arrow_field)
                .try_collect::<Vec<_>>()?,
        )))
    }

    pub(crate) fn to_arrow_schema_ref(&self) -> PyResult<ArrowSchemaRef> {
        Ok(Arc::new(self.to_arrow_schema()?))
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SchemaDef>()?;
    m.add_class::<Field>()?;
    m.add_class::<DataType>()?;
    Ok(())
}

import os

from unittest import mock
from unittest.mock import MagicMock

from mlflow.tracking import MlflowClient

from pytorch_lightning import Trainer
from pytorch_lightning.loggers import MLFlowLogger
from tests.base import EvalModelTemplate


@mock.patch('pytorch_lightning.loggers.mlflow.mlflow')
@mock.patch('pytorch_lightning.loggers.mlflow.MlflowClient')
def test_mlflow_logger_exists(client, mlflow, tmpdir):
    """ Test launching three independent loggers with either same or different experiment name. """

    run1 = MagicMock()
    run1.info.run_id = "run-id-1"

    run2 = MagicMock()
    run2.info.run_id = "run-id-2"

    run3 = MagicMock()
    run3.info.run_id = "run-id-3"

    # simulate non-existing experiment creation
    client.return_value.get_experiment_by_name = MagicMock(return_value=None)
    client.return_value.create_experiment = MagicMock(return_value="exp-id-1")  # experiment_id
    client.return_value.create_run = MagicMock(return_value=run1)

    logger = MLFlowLogger('test', save_dir=tmpdir)
    assert logger._experiment_id is None
    assert logger._run_id is None
    _ = logger.experiment
    assert logger.experiment_id == "exp-id-1"
    assert logger.run_id == "run-id-1"
    assert logger.experiment.create_experiment.asset_called_once()
    client.reset_mock(return_value=True)

    # simulate existing experiment returns experiment id
    exp1 = MagicMock()
    exp1.experiment_id = "exp-id-1"
    client.return_value.get_experiment_by_name = MagicMock(return_value=exp1)
    client.return_value.create_run = MagicMock(return_value=run2)

    # same name leads to same experiment id, but different runs get recorded
    logger2 = MLFlowLogger('test', save_dir=tmpdir)
    assert logger2.experiment_id == logger.experiment_id
    assert logger2.run_id == "run-id-2"
    assert logger2.experiment.create_experiment.call_count == 0
    assert logger2.experiment.create_run.asset_called_once()
    client.reset_mock(return_value=True)

    # simulate a 3rd experiment with new name
    client.return_value.get_experiment_by_name = MagicMock(return_value=None)
    client.return_value.create_experiment = MagicMock(return_value="exp-id-3")
    client.return_value.create_run = MagicMock(return_value=run3)

    # logger with new experiment name causes new experiment id and new run id to be created
    logger3 = MLFlowLogger('new', save_dir=tmpdir)
    assert logger3.experiment_id == "exp-id-3" != logger.experiment_id
    assert logger3.run_id == "run-id-3"


def test_mlflow_logger_dirs_creation(tmpdir):
    """ Test that the logger creates the folders and files in the right place. """
    assert not os.listdir(tmpdir)
    logger = MLFlowLogger('test', save_dir=tmpdir)
    assert logger.save_dir == tmpdir
    assert set(os.listdir(tmpdir)) == {'.trash'}
    run_id = logger.run_id
    exp_id = logger.experiment_id

    # multiple experiment calls should not lead to new experiment folders
    for i in range(2):
        _ = logger.experiment
        assert set(os.listdir(tmpdir)) == {'.trash', exp_id}
        assert set(os.listdir(tmpdir / exp_id)) == {run_id, 'meta.yaml'}

    model = EvalModelTemplate()
    trainer = Trainer(default_root_dir=tmpdir, logger=logger, max_epochs=1, limit_val_batches=3)
    trainer.fit(model)
    assert set(os.listdir(tmpdir / exp_id)) == {run_id, 'meta.yaml'}
    assert 'epoch' in os.listdir(tmpdir / exp_id / run_id / 'metrics')
    assert set(os.listdir(tmpdir / exp_id / run_id / 'params')) == model.hparams.keys()
    assert trainer.checkpoint_callback.dirpath == (tmpdir / exp_id / run_id / 'checkpoints')
    assert set(os.listdir(trainer.checkpoint_callback.dirpath)) == {'epoch=0.ckpt'}


def test_mlflow_experiment_id_retrieved_once(tmpdir):
    logger = MLFlowLogger('test', save_dir=tmpdir)
    get_experiment_name = logger._mlflow_client.get_experiment_by_name
    with mock.patch.object(MlflowClient, 'get_experiment_by_name', wraps=get_experiment_name) as mocked:
        _ = logger.experiment
        _ = logger.experiment
        _ = logger.experiment
        assert mocked.call_count == 1

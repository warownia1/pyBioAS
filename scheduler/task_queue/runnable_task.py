class RunnableTask(object):

    def run(self, *args, **kwargs):
        """
        Launches the task and returns it's result.
        Method should be blocking.
        :param args: task's arguments
        :param kwargs: task's positional arguments
        :return: task result
        """
        raise NotImplementedError

    def kill(self):
        """
        Kills the execution of the task.
        """
        raise NotImplementedError

    def suspend(self):
        """
        Blocks the execution of the task
        """
        raise NotImplementedError

    def resume(self):
        """
        Resumes the execution of the suspended task
        """
        raise NotImplementedError

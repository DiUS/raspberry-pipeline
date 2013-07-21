# deals with messages that are generated by:
# https://github.com/jkelabora/snsnotify-plugin

import re
from lib.pipeline import Pipeline
from sounds.player import Player
import logging
from datetime import datetime
from unrecognised_directive_exception import UnrecognisedDirective

# pick out the required parts from the snsnotify-plugin messages
jenkins_regex = r"Build ([A-Z]+): (.*) #"

# the keys here are from the snsnotify-plugin, the values need to match the base_message_interface colours
jenkins_colours = {
    'FAILURE' : 'red',
    'SUCCESS' : 'green',
    'ABORTED' : 'white'
}

# the entries in STAGES need to be case-sensitive matches of the jenkins build names
first_pipeline = {
    'IDENTIFIER' : 'WF',
    'OFFSET' : 0,
    'STAGE_WIDTH' : 2,
    'STAGES' : [ 'WF - Prepare', 'WF - Unit Tests', 'WF - Integration Tests', 'WF - Deploy Test', 'WF - Deploy to QA', 'WF - Deploy to Production' ]
}

# the entries in STAGES need to be case-sensitive matches of the jenkins build names
second_pipeline = {
    'IDENTIFIER' : 'RM',
    'OFFSET' : 10,
    'STAGE_WIDTH' : 2,
    'STAGES' : [ 'RM - Prepare', 'RM - Unit Tests', 'RM - Integration Tests', 'RM - Deploy Test', 'RM - Deploy to QA', 'RM - Deploy to Production' ]
}

third_pipeline = {
    'IDENTIFIER' : 'DT',
    'OFFSET' : 20,
    'STAGE_WIDTH' : 2,
    'STAGES' : [ 'DT - Prepare', 'DT - Unit Tests', 'DT - Deploy Test', 'DT - Deploy to QA', 'DT - Deploy to Production' ]
}

class JenkinsMessageTranslator:

    def __init__(self, reporter_q):
        self.pipelines = [ Pipeline(first_pipeline), Pipeline(second_pipeline), Pipeline(third_pipeline) ]
        self.sound_player = Player()
        self.reporter_q = reporter_q

    def issue_directive(self, directive, play_sound=False):
        if directive == 'all_off':
            for pipeline in self.pipelines:
                pipeline.issue_all_off()
            self.reporter_q.put(self.__current_state())
            return

        pipeline = self.__determine_pipeline(directive)
        segment_number = self.__determine_segment_number(pipeline, directive)

        if segment_number == 0:
            pipeline.issue_start_build()
            if play_sound:
              self.sound_player.play_random_start_sound()
            self.reporter_q.put(self.__current_state())
            return

        colour = self.__determine_colour(directive)
        if play_sound:
          if colour == 'green':
            self.sound_player.play_random_success_sound()
          elif colour == 'red':
            self.sound_player.play_random_failure_sound()

        if segment_number == 1:
            pipeline.issue_all_stages_update(colour)
            self.reporter_q.put(self.__current_state())
            return

        pipeline.issue_update_segment(segment_number, colour)
        self.reporter_q.put(self.__current_state())

    def __determine_pipeline(self, directive):
        build_name = re.search(jenkins_regex, directive).group(2)
        for pipeline in self.pipelines:
            if pipeline.matches(build_name): return pipeline
        logging.getLogger().error("problem determining pipeline for directive: {0}".format(directive))
        raise UnrecognisedDirective

    def __determine_segment_number(self, pipeline, directive):
        match = re.search(jenkins_regex, directive)
        if match is None or match.group(2) not in pipeline.detail['STAGES']:
            logging.getLogger().error("problem determining segment for directive: {0}".format(directive))
            raise UnrecognisedDirective
        return pipeline.detail['STAGES'].index(match.group(2))

    def __determine_colour(self, directive):
        match = re.search(jenkins_regex, directive)
        return jenkins_colours[match.group(1)]

    def __current_state(self):
        state_of_all_pipelines = {}
        for pipeline in self.pipelines:
            state_of_all_pipelines.update(pipeline.current_state())
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return { "recorded_at" : now, "name" : "fmsystems", "pipelines" : state_of_all_pipelines }

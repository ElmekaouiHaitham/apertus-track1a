.PHONY: run test report live
run:
	$(MAKE) -C track_1a run
test:
	$(MAKE) -C track_1a test
report:
	$(MAKE) -C track_1a report
live:
	$(MAKE) -C track_1a live

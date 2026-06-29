BIN := fs_link

.PHONY: all build test vet fmt install clean

all: build

build:
	go build -o $(BIN) .

test:
	go test ./...

vet:
	go vet ./...

fmt:
	gofmt -l -w .

install:
	go install .

clean:
	rm -f $(BIN)
	go clean

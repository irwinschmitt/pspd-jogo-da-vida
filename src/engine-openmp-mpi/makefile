CC = mpicc
CFLAGS = -Wall -fopenmp
LDFLAGS = -ljansson
TARGET = jogo_da_vida.o
SRC = jogo_da_vida.c
WORKER_COUNT = 4

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(TARGET)

run:
	mpirun -np $(WORKER_COUNT) ./$(TARGET) 5000

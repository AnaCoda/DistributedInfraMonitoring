use std::{thread, time::Duration};

fn main() {
    loop {
        println!("Hello world!");
        thread::sleep(Duration::from_secs(1));
    }
}
